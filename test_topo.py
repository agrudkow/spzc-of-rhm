from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node, RemoteController
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.util import quietRun

def checkRequired():
    "Check for required executables"
    required = [ 'dnslib']
    for r in required:
        print(quietRun( 'pip install ' + r ))


class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


class NetworkTopo(Topo):
    def build(self, **_opts):
        # Add 2 routers in two different subnets
        r1 = self.addHost('r1', cls=LinuxRouter, ip='10.0.0.1/16')

        # Add 2 switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        # Add host-switch links in the same subnet
        self.addLink(s1,
                     r1,
                     intfName2='r1-eth1',
                     params2={'ip': '10.0.0.1/16'})

        self.addLink(s2,
                     r1,
                     intfName2='r1-eth2',
                     params2={'ip': '10.1.0.1/16'})

        # Adding hosts specifying the default route
        d1 = self.addHost(name='d1',
                          ip='10.0.0.251/16')
        d2 = self.addHost(name='d2',
                          ip='10.0.0.252/16')
        d3 = self.addHost(name='d3',
                          ip='10.1.0.253/16')
        d4 = self.addHost(name='d4',
                          ip='10.1.0.254/16')

        # Add DNS
        dns = self.addHost(name='dns', ip='10.0.0.2/16')

        # Add dns-switch links
        self.addLink(dns, s1)

        # Add host-switch links
        self.addLink(d1, s1)
        self.addLink(d2, s1)
        self.addLink(d3, s2)
        self.addLink(d4, s2)

def runDNS(host):
    host.cmd('python2 dns_mock.py --udp --tcp --port 53 &')

def addRoute(hosts):
    gatwayIPs = {
        'dns': ['10.1.0.0', '10.0.0.1'],
        'd1': ['10.1.0.0', '10.0.0.1'], 
        'd2': ['10.1.0.0', '10.0.0.1'], 
        'd3': ['10.0.0.0', '10.1.0.1'], 
        'd4': ['10.0.0.0', '10.1.0.1'], 
    }
    for host in hosts:
        host.cmd('ip route add {}/16 via {}'.format(gatwayIPs[str(host)][0], gatwayIPs[str(host)][1]))

def run():
    checkRequired()

    topo = NetworkTopo()
    net = Mininet(topo=topo, controller=RemoteController)

    hosts = net.get('dns', 'd1', 'd2', 'd3', 'd4')
    net.addNAT().configDefault()

    net.start()

    # runDNS(hosts[0])
    addRoute(hosts)
    net.pingAll()

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()
