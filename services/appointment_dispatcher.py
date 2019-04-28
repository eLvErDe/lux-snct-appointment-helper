"""
Receive scrapper updates and dispatch new appointments offers to clients
"""


# pylint: disable=line-too-long


import logging
import asyncio


class AppointmentDispatcher:
    """
    Receive scrapper updates and dispatch new appointments offers to clients
    """

    def __init__(self):

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sites = []
        self.vehicle_types = []
        self.appointments = {}

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

    def appointment_handler(self, payload, exc):
        """ Will be attached to SNCT scrapper and receive dict of available appointments slots """

        if exc is None:
            self.logger.info("Updated appointments received")
            self.appointments = payload

        for client, criterias in self.appointments_clients.items():
            asyncio.ensure_future(client.push_appointments(self.appointments))

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
