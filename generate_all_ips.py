import struct, socket
# https://stackoverflow.com/a/17641585/12956601
def generate_all_ips(start, end):
  '''
  Generaate ips in a given range.

  @param start - fist ip in a range
  @param end - next ip after last ip retruned by function (non-inclusive)
  '''
  start_ip = struct.unpack('>I', socket.inet_aton(start))[0]
  end_ip = struct.unpack('>I', socket.inet_aton(end))[0]
  ips = [socket.inet_ntoa(struct.pack('>I', i)) for i in range(start_ip, end_ip)]
  return ips