from pox.core import core
from pox.lib.packet.ethernet import ethernet
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

def _handle_ConnectionUp (event):
  dpid = event.connection.dpid 
  log.info('connection up ' + str(dpid))
  if dpid == 1:
    event.connection.send( of.ofp_flow_mod( action=of.ofp_action_output( port=5 ),
                                       priority=42,
                                       match=of.ofp_match( dl_type=0x800,
                                                           nw_dst="10.0.0.2")))
  if dpid == 2:
    event.connection.send( of.ofp_flow_mod( action=of.ofp_action_output( port=1 ),
                                           priority=42,
                                           match=of.ofp_match( dl_type=0x800,
                                                               nw_dst="10.0.0.2")))

def _handle_PacketIn (event):
  dpid = event.connection.dpid
  inport = event.port
  packet = event.parsed
  type = packet.type
  if packet.find('dns'):
      log.info('port:  {} switch:  {}'.format(inport,  dpid))
  if type == ethernet.ARP_TYPE:
      ip = packet.payload.protosrc
      dst = packet.payload.protodst
      log.info('srcip {} dstip: {};'.format(ip,dst))


def launch ():
  core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
  core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
  log.info("Reactive hub running.")
