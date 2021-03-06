# Copyright 2011-2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An L2 learning switch.
It is derived from one written live for an SDN crash course.
It is somwhat similar to NOX's pyswitch in that it installs
exact-match rules for each flow.
"""

from merge_dicts import merge_dicts
from generate_all_ips import generate_all_ips
from random_host_mutation import RandomHostMutation
from pox.core import core
from pox.lib.addresses import IPAddr, EthAddr
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str, str_to_dpid
from pox.lib.util import str_to_bool
import time
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet
from threading import Thread
log = core.getLogger()

# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0

v_ip = dict()

r_ip = dict()

HOSTS_S1 = ['10.0.0.251', '10.0.0.252']
HOSTS_S2 = ['10.1.0.253', '10.1.0.254']

IP_RANGE_HOSTS_S1 = ('10.0.2.0', '10.0.2.16')
IP_RANGE_HOSTS_S2 = ('10.1.2.0', '10.1.2.16')


DNS_IP = '10.0.0.2'

class IpMutation:
  def __init__(self):
    self._running = True

    v_ips_s1 = [ip for ip in generate_all_ips(*IP_RANGE_HOSTS_S1) if ip not in HOSTS_S1]
    self.rhm_s1 = RandomHostMutation(HOSTS_S1, v_ips_s1)

    v_ips_s2 = [ip for ip in generate_all_ips(*IP_RANGE_HOSTS_S2) if ip not in HOSTS_S2]
    self.rhm_s2 = RandomHostMutation(HOSTS_S2, v_ips_s2)
    
  def terminate(self):
    self._running = False
    
  def run(self):
    global v_ip, r_ip

    while self._running:
      r_ip = merge_dicts(self.rhm_s1.get_r_ips(), self.rhm_s2.get_r_ips())
      v_ip = merge_dicts(self.rhm_s1.get_v_ips(), self.rhm_s2.get_v_ips())

      self.rhm_s1.mutate()
      self.rhm_s2.mutate()
      
      time.sleep(5)
class LearningSwitch (object):
  """
  The learning switch "brain" associated with a single OpenFlow switch.
  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.
  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.
  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).
  In short, our algorithm looks like this:
  For each packet from the switch:
  1) Use source address and switch port to update address/port table
  2) Is transparent = False and either Ethertype is LLDP or the packet's
     destination address is a Bridge Filtered address?
     Yes:
        2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     6a) Send the packet out appropriate port
  """
  def __init__ (self, connection, transparent):
    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection
    self.transparent = transparent

    # Our tables
    self.macToPort = {}
    self.arpTable = {}

    # We want to hear PacketIn messages, so we listen
    # to the connection
    connection.addListeners(self)

    # We just use this to know when to log a helpful message
    self.hold_down_expired = _flood_delay == 0

    #log.debug("Initializing LearningSwitch, transparent=%s",
    #          str(self.transparent))

  def resend_packet (self, packet_in, out_port):
    """
    Instructs the switch to resend a packet that it had sent to us.
    "packet_in" is the ofp_packet_in object the switch had sent to the
    controller due to a table-miss.
    """
    msg = of.ofp_packet_out()
    msg.data = packet_in
    #check_dns = msg.data.find('dns')
    #if check_dns != None:
    #  msg.data.next.next.next.answers[0].name  = msg.data.next.next.next.answers[0].name.decode()
    # Add an action to send to the specified port
    action = of.ofp_action_output(port = out_port)
    msg.actions.append(action)

    # Send message to switch
    self.connection.send(msg)

  def send_packet (self, buffer_id, raw_data, out_port, in_port):
   """
   Sends a packet out of the specified switch port.
   If buffer_id is a valid buffer on the switch, use that.  Otherwise,
   send the raw data in raw_data.
   The "in_port" is the port number that packet arrived on.  Use
   OFPP_NONE if you're generating this packet.
   """
   msg = of.ofp_packet_out()
   msg.in_port = in_port
   if buffer_id != -1 and buffer_id is not None:
     # We got a buffer ID from the switch; use that
     msg.buffer_id = buffer_id
   else:
     # No buffer ID from switch -- we got the raw data
     if raw_data is None:
       # No raw_data specified -- nothing to send!
       return
     msg.data = raw_data
   action = of.ofp_action_output(port = out_port)
   msg.actions.append(action)
   
   # Send message to switch
   self.connection.send(msg)

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """

    packet = event.parsed

    def convert_vip_to_rip(vip):
      return v_ip[vip]

    def flood (message = None):
      """ Floods the packet """
      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time >= _flood_delay:
        if self.hold_down_expired is False:
          self.hold_down_expired = True
          log.info("%s: Flood hold-down expired -- flooding",
              dpid_to_str(event.dpid))

        if message is not None: log.debug(message)
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
      msg.data = event.ofp
      if isinstance(event.parsed.next, arp):
        log.debug('[FLOOD MSG.DATA]: event.parsed.next.protodst: {}'.format(event.parsed.next.protodst))
      msg.in_port = event.port
      self.connection.send(msg)

    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """
      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = duration[0]
        msg.hard_timeout = duration[1]
        msg.buffer_id = event.ofp.buffer_id
        self.connection.send(msg)
      elif event.ofp.buffer_id is not None:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        self.connection.send(msg)



    self.macToPort[packet.src] = event.port # 1
    if isinstance(packet.next, ipv4):
      self.arpTable[packet.next.srcip.toStr()] = packet.src
    log.debug("arpTable %s, switch %s" % (self.macToPort, self.connection.dpid))
    if not self.transparent: # 2
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        log.debug('[DROP]: packet type: {}, {} => {}'.format(packet.type, packet.next.protosrc, packet.next.protodst))
        drop() # 2a
        return

    if packet.dst.is_multicast:
      if isinstance(packet.next, arp) and packet.next.protodst.toStr() in v_ip:
        log.debug("ARP msg: %i %i %s => %s", self.connection.dpid, event.port, packet.next.protosrc, packet.next.protodst)
        protodst = packet.next.protodst
        dst_rip = IPAddr(convert_vip_to_rip(protodst.toStr()))
        if dst_rip.toStr() in self.arpTable:
          packet.dst = packet.src
          packet.src = self.arpTable[dst_rip.toStr()]
          packet.next.protodst = packet.next.protosrc
          packet.next.protosrc = protodst
          packet.next.hwdst = packet.next.hwsrc
          packet.next.hwsrc = self.arpTable[dst_rip.toStr()]
          packet.next.opcode = arp.REPLY
          msg = of.ofp_packet_out()
          msg.data = packet
          msg.actions.append(of.ofp_action_output(port = event.port))
          msg.in_port = 65535
          event.connection.send(msg)
      else:
        flood() # 3a
    else:
      if packet.dst not in self.macToPort: # 4
        flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: # 5
          # 5a
          log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
              % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
          drop(10)
          return
        # 6
        a_dns = packet.find('dns')
        if a_dns != None:
          if packet.next.srcip.toStr() == DNS_IP:
            log.debug("Its packet from dns server")
            log.debug(a_dns.answers)                 
            for answer in  a_dns.answers:
              log.debug(answer)
              if answer.qtype == 1:
                log.debug("Its A type dns dns dns") 
                if answer.rddata.toStr() in r_ip:
                  log.debug("change ip ip ip to vip")
                  log.debug(answer.rddata)
                  answer.rddata = IPAddr(r_ip[answer.rddata.toStr()]) 
                  log.debug(answer.rddata)
       
        log.debug("sending packet out for %s.%i -> %s.%i" %
                 (packet.src, event.port, packet.dst, port))

        if isinstance(packet.next, ipv4):
          if packet.next.dstip.toStr() in v_ip:
            packet.next.dstip = IPAddr(convert_vip_to_rip(packet.next.dstip.toStr()))
          if packet.next.srcip.toStr() in r_ip:
            packet.next.srcip = IPAddr(r_ip[ packet.next.srcip.toStr()])
          log.debug("IPv4 msg: %i %i IP %s => %s", self.connection.dpid, event.port,
                packet.next.srcip,packet.next.dstip)
       
        self.resend_packet(packet, port)
        
class l2_learning (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self, transparent, ignore = None):
    """
    Initialize
    See LearningSwitch for meaning of 'transparent'
    'ignore' is an optional list/set of DPIDs to ignore
    """
    core.openflow.addListeners(self)
    self.transparent = transparent
    self.ignore = set(ignore) if ignore else ()

  def _handle_ConnectionUp (self, event):
    if event.dpid in self.ignore:
      log.debug("Ignoring connection %s" % (event.connection,))
      return
    log.debug("Connection %s" % (event.connection,))
    LearningSwitch(event.connection, self.transparent)


def launch (transparent=False, hold_down=_flood_delay, ignore = None):
  """
  Starts an L2 learning switch.
  """
  try:
    global _flood_delay
    _flood_delay = int(str(hold_down), 10)
    assert _flood_delay >= 0
  except:
    raise RuntimeError("Expected hold-down to be a number")

  if ignore:
    ignore = ignore.replace(',', ' ').split()
    ignore = set(str_to_dpid(dpid) for dpid in ignore)
  
  c = IpMutation()
  t = Thread(target=c.run)
  t.daemon = True
  t.start()

  core.registerNew(l2_learning, str_to_bool(transparent), ignore)
