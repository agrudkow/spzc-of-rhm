from pox.core import core

log = core.getLogger()



def _handle_PacketIn (event):
  dpid = event.connection.dpid
  inport = event.port
  packet = event.parsed
  type = packet.type
  log.info('dpdi: {}; por : {}, type: {}'.format(dpid, inport, type))


def launch ():
  core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
  log.info("Reactive hub running.")