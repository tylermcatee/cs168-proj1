"""
Your awesome Distance Vector router for CS 168
"""

import sim.api as api
import sim.basics as basics


# We define infinity as a distance of 16.
INFINITY = 16

# For accessing a routes own maps
# Stored as -1 so that we can pass poisoned routes around
INSTANCE = -1

# Constants
DESTINATION_NOT_FOUND = 'DESTINATION_NOT_FOUND'

# Keys into route dictionary
kCost = 'cost'

# Abstractions for mapping
# Didn't really feel like making another class
kDistance = 'kDistance'
kNextHop = 'kNextHop'
kTime = 'kTime'
def m_mapping(distance, next_hop):
    return {
        kDistance : distance,
        kNextHop : next_hop,
        kTime : api.current_time(),
    }
def m_distance(mapping):
    return mapping[kDistance]
def m_next_hop(mapping):
    return mapping[kNextHop]
def m_time(mapping):
    return mapping[kTime]
def m_update_time(mapping):
    mapping[kTime] = api.current_time()

class RouteMap:
    """
    Keeps track of the topology of the system as viewed
    from a particular DVRouter

    Takes a delegate that can execute the following method signatures:
        route_update(self, host)
    """
    def __init__(self, delegate):
        self.latencies = {
            INSTANCE : 0
        }
        self.delegate = delegate

        # Map ports to stored host->port mappings
        # Keep 'self' as the key to our own stored host->port mappings
        self.routes = {
            INSTANCE : {}
        }
        pass

    def received_route(self, port, host, latency):
        """
        When we received a RoutePacket, update route information.
        """

        # If we haven't seen before
        if host not in self.routes[port]:
            for _port in self.routes:
                if host not in self.routes[_port]:
                    self.routes[_port][host] = m_mapping(distance=INFINITY, next_hop=port)

        # Update change to neighbor's distance vector
        mapping = self.routes[port][host]
        mapping[kDistance] = latency

        # See if we have a new shorter path, if so update everyone
        if self.update_route_for_host(host):
            self.delegate.route_update(host)

        # Update this routes last refreshed time
        m_update_time(mapping)


    def update_route_for_host(self, host):
        """
        Update shortest distance to host, return True if route
        distance changed.
        """
        mapping = self.routes[INSTANCE][host]
        original_distance = m_distance(mapping)
        mapping[kDistance] = INFINITY

        for port in self.routes:
            distance = self.latencies[port] + m_distance(self.routes[port][host])
            if distance < m_distance(mapping):
                mapping[kDistance] = distance
                mapping[kNextHop] = port
                self.routes[INSTANCE][host] = mapping

        return m_distance(mapping) != original_distance

    def host_discover(self, host, port):
        """
        When we receive a HostDiscoveryPacket, we need to add the
        host as this routers known hosts that are connected.
        """
        # This host can reach itself with length 0
        self.routes[port][host] = m_mapping(distance=0, next_hop=port)

        latency = self.latencies[port]

        if host not in self.routes[INSTANCE]:
            self.routes[INSTANCE][host] = m_mapping(distance=latency, next_hop=port)
            for port in self.routes:
                if host not in self.routes[port]:
                    self.routes[port][host] = m_mapping(distance=INFINITY, next_hop=port)
        else:
            # Update path distance if path is shorter
            old_mapping = self.routes[INSTANCE][host]
            if latency < m_distance(mapping):
                new_mapping = m_mapping(distance=latency, next_hop=port)
                self.routes[INSTANCE][host] = new_mapping

        self.delegate.route_update(host)

    def add_link(self, port, latency):
        """
        When handle_link_up is called, we need to add it
        to our routemap and send out the appropriate updates
        """
        self.latencies[port] = latency
        # For each of the hosts we currently know about, add
        # infinity distance to this links mapping
        self.routes[port] = {}
        new_entry = self.routes[port]
        for host in self.routes[INSTANCE]:
            new_entry[host] = m_mapping(distance=INFINITY, next_hop=port)
            self.delegate.route_update(host)


    def latency(self, port):
        """
        Returns the latency for link on port
        """
        return self.latencies[port]

    def connected_hosts(self):
        """
        Return a list of ports that connect directly to hosts
        on this router.
        """
        connected_hosts = []
        # Get the host to port mappings for ourself
        host_to_port = self.routes[INSTANCE]
        # Return all the next hops with distance 1
        for mapping in host_to_port.values():
            if m_distance(mapping) == 1:
                connected_hosts.append(m_next_hop(mapping))
        return connected_hosts

    def next_hop(self, host):
        """
        Returns the next hop port to reach host
        from this router.
        """
        # Get the host to port mappings for ourself
        host_to_port = self.routes[INSTANCE]

        if host not in host_to_port:
            # We have not seen this destination yet
            return DESTINATION_NOT_FOUND

        return host_to_port[host]

    def mapping_for_host(self, host):
        return self.routes[INSTANCE][host]

class DVRouter (basics.DVRouterBase):
    NO_LOG = False # Set to True on an instance to disable its logging
    POISON_MODE = False # Can override POISON_MODE here
    DEFAULT_TIMER_INTERVAL = 5 # Can override this yourself for testing

    def __init__ (self):
        """
        Called when the instance is initialized.

        You probably want to do some additional initialization here.
        """
        # Create a routemap
        self.route_map = RouteMap(self)
        # Starts calling handle_timer() at correct rate
        self.start_timer()

    def handle_link_up (self, port, latency):
        """
        Called by the framework when a link attached to this Entity goes up.

        The port attached to the link and the link latency are passed in.
        """
        if not self.NO_LOG:
            self.log("handle_link_up on %s (%s)" % (port, api.current_time()))
        self.route_map.add_link(port, latency)

    def handle_link_down (self, port):
        """
        Called by the framework when a link attached to this Entity does down.

        The port number used by the link is passed in.
        """
        if not self.NO_LOG:
            self.log("handle_link_down on %s (%s)" % (port, api.current_time()))
        # self.route_map.remove_link(port, latency) # TODO:

    def handle_rx (self, packet, port):
        """
        Called by the framework when this Entity receives a packet.

        packet is a Packet (or subclass).
        port is the port number it arrived on.

        You definitely want to fill this in.
        """
        if isinstance(packet, basics.RoutePacket):
            self.handle_route_packet(packet, port)
            return
        elif isinstance(packet, basics.HostDiscoveryPacket):
            self.handle_host_discover_packet(packet, port)
            return
        else:
            if not self.NO_LOG:
                self.log("RX UNKNOWN %s on %s (%s)", packet, port, api.current_time())
            
            host = packet.dst
            mapping = self.route_map.next_hop(host)
            if mapping == DESTINATION_NOT_FOUND:
                self.send(packet, port, flood=True)
            next_hop = m_next_hop(mapping)
            if next_hop != port:
                self.send(packet, next_hop)
            elif self.POISON_MODE:
                # The correct route is sending the packet back to the port
                # we received it on. We need to poison this route
                poison_packet = basics.RoutePacket(host, INFINITY)
                self.send(poison_packet, port)

    def handle_route_packet(self, packet, port):
        if not self.NO_LOG:
            self.log("RX RoutePacket %s on %s (%s)", packet, port, api.current_time())
        host = packet.destination
        latency = packet.latency
        # Notify the route map of the new route
        self.route_map.received_route(port, host, latency)

    def handle_host_discover_packet(self, packet, port):
        if not self.NO_LOG:
            self.log("RX HostDiscoveryPacket %s on %s (%s)", packet, port, api.current_time())
        host = packet.src
        # Notify the route map of the new host
        self.route_map.host_discover(host, port)

    def handle_timer (self):
        """
        Called periodically.

        When called, your router should send tables to neighbors.  It also might
        not be a bad place to check for whether any entries have expired.
        """
        # Check whether any entires have expired
        self.check_if_entries_expired()
        # Send tables to neighbors
        self.send_tables_to_neighbors()

    def check_if_entries_expired(self):
        return

    def send_tables_to_neighbors(self):
        return

    def route_update(self, host):
        """
        Send out RoutePacket indicating update to route to 'host'
        """
        mapping = self.route_map.mapping_for_host(host)
        route_packet = basics.RoutePacket(host, m_distance(mapping))
        if m_distance(mapping) < INFINITY:
            # Flood the packet
            self.send(route_packet, m_next_hop(mapping), flood=True)

        if self.POISON_MODE:
            if m_distance(mapping) != INFINITY:
                # Poisoned Reverse
                poison_packet = basics.RoutePacket(host, INFINITY)
                self.send(poison_packet, m_next_hop(mapping))
            else:
                # Poisoned Route
                self.send(route_packet, INSTANCE, flood=True)

