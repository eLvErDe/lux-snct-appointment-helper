"""
Define the REST API for JWT authentication
"""


# pylint: disable=line-too-long


import asyncio
import logging
import functools
import inspect
import aiohttp.web
import aiohttp_swagger
import aiohttp_cors
import api_middlewares
import resources
import services


class ApiFactory(object):
    """
    Define the REST API for Snct appointments helper
    """

    def __init__(self, loop=None, config=None):
        """ Create the aiohttp application """

        self.logger = logging.getLogger(self.__class__.__name__)
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.config = config

        swagger_url = self.prefix_context_path("/doc")

        self.app = aiohttp.web.Application(loop=loop, middlewares=[functools.partial(api_middlewares.rest_error_middleware, logger=self.logger)])
        self.app.factory = self

        self.app.router.add_route("GET", "/", lambda x: aiohttp.web.HTTPFound(swagger_url))
        if self.config.context_path != "/":
            self.app.router.add_route("GET", self.config.context_path, lambda x: aiohttp.web.HTTPFound(swagger_url))
        self.app.router.add_route("GET", self.config.context_path + "/", lambda x: aiohttp.web.HTTPFound(swagger_url))
        self.app.router.add_route(
            "GET",
            self.prefix_context_path("/appointments/{user_type}/{control_type}/{vehicle_type}/{organism}/{site}/{start_date}/{end_date}"),
            resources.RestAppointments().get,
        )
        self.app.router.add_route("GET", self.prefix_context_path("/sites"), resources.RestSites().get)
        self.app.router.add_route("GET", self.prefix_context_path("/appointments/ws"), resources.WsAppointments().get)

        # Setup Swagger
        # bundle_params and schemes are a GitHub patch not released
        # in any aiohttp_swagger package
        setup_swagger_sign = inspect.signature(aiohttp_swagger.setup_swagger)
        kwargs = {}
        if "bundle_params" in setup_swagger_sign.parameters:
            kwargs["bundle_params"] = {"layout": "BaseLayout", "defaultModelExpandDepth": 5}
        if "schemes" in setup_swagger_sign.parameters:
            kwargs["schemes"] = self.config.swagger_ui_schemes

        aiohttp_swagger.setup_swagger(
            app=self.app,
            description="API for finding appointments timeslots for SNCT vehicule inspection",
            title="SNCT Appointments API",
            api_version="1.0",
            contact="acecile@letz-it.lu",
            swagger_url=swagger_url,
            **kwargs
        )

        # Setup CORS
        if self.config.allow_origin:
            self.cors = aiohttp_cors.setup(
                self.app,
                defaults={self.config.allow_origin: aiohttp_cors.ResourceOptions(allow_credentials=True, expose_headers="*", allow_headers="*")},
            )
            for route in self.app.router.routes():
                if not isinstance(route.resource, aiohttp.web_urldispatcher.StaticResource):
                    self.cors.add(route)

        # Print configured routes
        self.print_routes()

        # Setup services
        self.app.on_startup.append(self.setup_appointment_dispatcher)
        self.app.on_startup.append(self.setup_snct_appointment_scrapper)
        self.app.on_shutdown.append(self.close_snct_appointment_scrapper)
        self.app.on_startup.append(self.setup_ws_stream_coros)
        self.app.on_shutdown.append(self.close_ws_stream_coros)

    def url_for(self, name):
        """ Get relative URL for a given route named """
        return self.app.router.named_resources()[name].url()

    @staticmethod
    def route_join(*args):
        """ Simple helper to compute relative URLs """
        route_url = "/".join([x.strip("/") for x in args])
        if not route_url.startswith("/"):
            route_url = "/" + route_url
        return route_url

    def prefix_context_path(self, *args):
        """ Construct a relative URL with context path """
        return self.route_join(self.config.context_path, *args)

    def print_routes(self):
        """ Log all configured routes """

        for route in self.app.router.routes():
            route_info = route.get_info()
            if "formatter" in route_info:
                url = route_info["formatter"]
            elif "path" in route_info:
                url = route_info["path"]
            elif "prefix" in route_info:
                url = route_info["prefix"]
            else:
                url = "Unknown type of route %s" % route_info

            self.logger.info("Route has been setup %s at %s", route.method, url)

    async def setup_appointment_dispatcher(self, app):
        """ Class receiving updates from SNCT scrapper and dispatching appointments to clients """

        app["apptm_disp"] = services.AppointmentDispatcher()

    @staticmethod
    async def setup_snct_appointment_scrapper(app):
        """ Initialize SNCT website scrapper and do mandatory pre-start calls """

        app["snct_scrapper"] = services.SnctAppointmentScrapper(
            site_handler=app["apptm_disp"].site_handler,
            vehicle_handler=app["apptm_disp"].vehicle_handler,
            appointment_handler=app["apptm_disp"].appointment_handler,
        )

        await app["snct_scrapper"].refresh_sites()
        await app["snct_scrapper"].refresh_vehicles()
        await app["snct_scrapper"].refresh_appointments()

        async def start_periodically_refresh_appointments():  # pylint: disable=invalid-name
            """ Refresh appointments every minutes """
            await asyncio.sleep(60)
            await app["snct_scrapper"].refresh_appointments_every_minutes()

        app.refresh_appointments_task = asyncio.ensure_future(start_periodically_refresh_appointments())

    @staticmethod
    async def close_snct_appointment_scrapper(app):
        """ Shutdown SNCT website scrapper """

        await asyncio.shield(app["snct_scrapper"].close())
        app.refresh_appointments_task.cancel()

    @staticmethod
    async def setup_ws_stream_coros(app):
        """
        Store all connected WS client here
        This is intended to properly close them on shutdown
        """

        app["ws_stream_coro"] = set()

    async def close_ws_stream_coros(self, app):
        """
        Close all WS clients
        """
        for coro in app["ws_stream_coro"]:
            self.logger.info("Closing WsAppointments websocket client")
            coro.cancel()
