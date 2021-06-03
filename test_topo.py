from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.util import quietRun
def checkRequired():
    "Check for required executables"
    required = [ 'udhcpd', 'udhcpc', 'dnsmasq', 'curl', 'firefox' ]
    for r in required:
        if not quietRun( 'which ' + r ):
            print('{} Installing'.format(r))
            print(quietRun( 'apt-get install -y ' + r ))
            if r == 'dnsmasq':
                # Don't run dnsmasq by default!
                print(quietRun('update-rc.d dnsmasq disable' ))


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
        r1 = self.addHost('r1', cls=LinuxRouter, ip='10.0.0.1/24')

        # Add 2 switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        # Add host-switch links in the same subnet
        self.addLink(s1,
                     r1,
                     intfName2='r1-eth1',
                     params2={'ip': '10.0.0.1/24'})

        self.addLink(s2,
                     r1,
                     intfName2='r1-eth2',
                     params2={'ip': '10.1.0.1/24'})

        # Adding hosts specifying the default route
        d1 = self.addHost(name='d1',
                          ip='10.0.0.251/24',
                          defaultRoute='via 10.0.0.1')
        d2 = self.addHost(name='d2',
                          ip='10.0.0.252/24',
                          defaultRoute='via 10.0.0.1')
        d3 = self.addHost(name='d3',
                          ip='10.1.0.253/24',
                          defaultRoute='via 10.1.0.1')
        d4 = self.addHost(name='d4',
                          ip='10.1.0.254/24',
                          defaultRoute='via 10.1.0.1')

        # Add DNS
        dns = self.addHost(name='dns', ip='10.0.0.2/24', defaultRoute='via 10.0.0.1')

        # Add dns-switch links
        self.addLink(dns, s1)

        # Add host-switch links
        self.addLink(d1, s1)
        self.addLink(d2, s1)
        self.addLink(d3, s2)
        self.addLink(d4, s2)

def runDNS(host):
    host.cmd('python3 dns_mock.py --udp --tcp --port 53')

def run():
    topo = NetworkTopo()
    net = Mininet(topo=topo)

    dns = net.get('dns')

    net.addNAT().configDefault()

    net.start()

    runDNS(dns)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run()