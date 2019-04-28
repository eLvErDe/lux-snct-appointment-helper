"""
Receive scrapper updates and dispatch new appointments offers to clients
"""


# pylint: disable=line-too-long


import logging
import collections
import asyncio


class AppointmentDispatcher:
    """
    Receive scrapper updates and dispatch new appointments offers to clients
    """

    def __init__(self):

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sites = []
        self.vehicle_types = []
        self.appointments = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(dict)))

        self.appointments_clients = {}

    def site_handler(self, payload, exc):
        """ Will be attached to SNCT scrapper and receive list of SNCT sites """

        if exc is None:
            self.logger.info("Updated sites received")
            self.sites = payload

    def vehicle_handler(self, payload, exc):
        """ Will be attached to SNCT scrapper and receive list of types of vehicules """

        if exc is None:
            self.logger.info("Updated vehicle types received")
            self.vehicle_types = payload

    def appointment_handler(self, payload):
        """ Will be attached to SNCT scrapper and receive dict of available appointments slots """

        self.logger.info("Updated appointments received")

        new_appointments_to_publish = []
        removed_appointments_to_publish = []

        for user_type in payload:  # pylint: disable=too-many-nested-blocks
            for control_type in payload[user_type]:
                for vehicle_type in payload[user_type][control_type]:
                    for site in payload[user_type][control_type][vehicle_type]:

                        orig_appointments = self.appointments[user_type][control_type][vehicle_type].get(site, None)
                        new_appointments = payload[user_type][control_type][vehicle_type][site]

                        # First call for this site
                        if orig_appointments is None:
                            self.appointments[user_type][control_type][vehicle_type][site] = new_appointments
                            self.logger.info("Initial appointments update for %s/%s %s/%s/%s", site[0], site[1], user_type, control_type, vehicle_type)
                            continue

                        # None in payload instead of list, refresh failed
                        if new_appointments is None:
                            self.logger.warning("Ignoring %s/%s %s/%s/%s, refresh seems to have failed", site[0], site[1], user_type, control_type, vehicle_type)
                            continue

                        added = [x for x in new_appointments if x not in orig_appointments]
                        removed = [x for x in orig_appointments if x not in new_appointments]

                        if added:
                            self.logger.info("Found new appointments for %s/%s %s/%s/%s: %s", site[0], site[1], user_type, control_type, vehicle_type, [x.isoformat() for x in added])
                            for timestamp in added:
                                new_appointments_to_publish.append({
                                    "user_type": user_type,
                                    "control_type": control_type,
                                    "vehicle_type": vehicle_type,
                                    "organism": site[0],
                                    "site": site[1],
                                    "timestamp": timestamp,
                                })
                        if removed:
                            self.logger.info("Found removed appointments for %s/%s %s/%s/%s: %s", site[0], site[1], user_type, control_type, vehicle_type, [x.isoformat() for x in removed])
                            for timestamp in removed:
                                removed_appointments_to_publish.append({
                                    "user_type": user_type,
                                    "control_type": control_type,
                                    "vehicle_type": vehicle_type,
                                    "organism": site[0],
                                    "site": site[1],
                                    "timestamp": timestamp,
                                })

                        self.appointments[user_type][control_type][vehicle_type][site] = new_appointments

        if new_appointments_to_publish:
            self.push_appointments_criterias(new_appointments_to_publish, cat="added")
        if removed_appointments_to_publish:
            self.push_appointments_criterias(new_appointments_to_publish, cat="removed")

    def push_appointments_criterias(self, appointments, cat="added"):
        """ Iterate over all clients and push updates to client with matching criterias """

        for client_handler, criterias in self.appointments_clients.items():
            filtered = []
            for criteria in criterias:
                for appointment in appointments:
                    condition = [
                        criteria["user_type"] == appointment["user_type"],
                        criteria["control_type"] == appointment["control_type"],
                        criteria["vehicle_type"] == appointment["vehicle_type"],
                        criteria["organism"] == appointment["organism"],
                        criteria["site"] == appointment["site"],
                        appointment["timestamp"] >= criteria["start_dt"],
                        appointment["timestamp"] <= criteria["end_dt"],
                    ]
                    if all(condition):
                        filtered.append(appointment)
                        self.logger.info("Found %s appointment for handler %s: %s", cat, client_handler, appointment)

            if filtered:
                if cat == "added":
                    asyncio.ensure_future(client_handler.push_appointments(added=appointments))
                else:
                    asyncio.ensure_future(client_handler.push_appointments(removed=appointments))

    def register_appointment_client(self, handler, criterias):
        """ Register a new client for appointments update """

        assert hasattr(handler, "push_appointments"), "handler must be an instance of class implementing push_appointments method"
        assert isinstance(criterias, list), "criterias must be a list of dict"
        assert all([isinstance(x, dict) for x in criterias]), "criterias must be a list of dict"

        self.appointments_clients[handler] = criterias
        self.logger.info("New %s client registered", handler.__class__.__name__)

    def unregister_appointment_client(self, handler):
        """ Register a new client for appointments update """

        self.logger.info("A client %s unregistered", handler.__class__.__name__)
        self.appointments_clients.pop(handler, None)
