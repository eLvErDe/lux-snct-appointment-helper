"""
Receive scrapper updates and dispatch new appointments offers to clients
"""


import logging


class AppointmentDispatcher:
    """
    Receive scrapper updates and dispatch new appointments offers to clients
    """

    def __init__(self):

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sites = []
        self.vehicle_types = []
        self.appointments = {}

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
