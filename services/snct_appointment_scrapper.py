"""
aiohttp asynchronous Bsoch RCP+ client
For dome camera PTZ handling
"""


# pylint: disable=line-too-long


import logging
import asyncio
import functools
import collections
import unicodedata
import datetime
import pytz
import aiohttp


class SnctAppointmentScrapper:  # pylint: disable=too-many-instance-attributes
    """
    Connect to SNCT API to find incoming free appointment timeframes and push them to handler
    Also take care of updating SNCT list of center and accepted vehicles types
    """

    def __init__(self, site_handler=None, vehicle_handler=None, appointment_handler=None):

        # Defaults to local handlers doing nothing but writing logs
        if site_handler is None:
            self.site_handler = self._site_handler
        if vehicle_handler is None:
            vehicle_handler = self._vehicle_handler
        if appointment_handler is None:
            appointment_handler = self._appointment_handler

        assert callable(site_handler), "site_handler must be a callable handling payload and exc arguments"
        assert callable(vehicle_handler), "vehicle_handler must be a callable handling payload and exc arguments"
        assert callable(appointment_handler), "appointment_handler must be a callable handling payload and exc arguments"

        self.site_handler = site_handler
        self.vehicle_handler = vehicle_handler
        self.appointment_handler = appointment_handler

        self.url = "https://rdv.snct.lu"
        self.timeout = 10
        self.concurrency = 10
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))
        self.logger = logging.getLogger(self.__class__.__name__)
        self.closed = False
        self.semaphore = asyncio.Semaphore(value=self.concurrency)

        self.site_list = {}
        self.vehicle_list = {}

    async def close(self):
        """ Kill asyncio session on shutdown """
        self.closed = True
        await self.session.close()

    @property
    def today_lux_date(self):
        """ Return today date properly formatted for SNCT API as local Luxembourg time """
        return datetime.datetime.now(tz=pytz.timezone("Europe/Luxembourg")).date().isoformat()

    @property
    def two_month_later_lux_date(self):
        """ Return two months offsetted date properly formatted for SNCT API as local Luxembourg time """
        return (datetime.datetime.now(tz=pytz.timezone("Europe/Luxembourg")).date() + datetime.timedelta(weeks=10)).isoformat()

    @property
    def site_list_url(self):
        """ Return API url providing list of sites """
        return self.url + "/rdvct/secure/admin/site/list"

    @property
    def vehicle_list_url(self):
        """ Return API url providing list of vehicles """
        return self.url + "/rdvct/secure/admin/vehicle/type/list"

    @property
    def vehicle_appointment_url_template(self):  # pylint: disable=invalid-name
        """ Return API url template (to use with .format() providing list of free appoitments frames """
        return self.url + "/rdvct/appointment/betweenDates/{start_dt}/{end_dt}/{vehicle_type}/{site_id}/{request_type}/{control_type}"

    def _dummy_handler(self, payload, exc, data_type="undefined"):
        """ Dummy handler for receiving data updates """

        assert payload is None or isinstance(payload, (dict, list)), "payload argument must be a dict or None"
        assert exc is None or isinstance(exc, Exception), "exc argument must be an Exception or None"
        self.logger.debug("Got payload for %s: %.80s... (exc: %s)", data_type, str(payload), exc)

    @property
    def _site_handler(self):
        """ Dummy handler for receiving site updates """
        return functools.partial(self._dummy_handler, data_type="site")

    @property
    def _vehicle_handler(self):
        """ Dummy handler for receiving vehicle updates """
        return functools.partial(self._dummy_handler, data_type="vehicle")

    @property
    def _appointment_handler(self):
        """ Dummy handler for receiving appoitment updates """
        return functools.partial(self._dummy_handler, data_type="appointment")

    async def _request(self, url):
        """
        Perform GET HTTP request on given URL
        Return a tuple (payload, exception) with None value if non-existing
        """

        if self.closed:
            return

        try:
            #self.logger.info("About to query %s, semaphore is %s", url, self.semaphore)
            async with self.semaphore:
                resp = await self.session.get(url, timeout=self.timeout)
            if resp.status == 200:
                try:
                    payload = await resp.json()
                except RuntimeError as exc:
                    # Looks like being a bug in asyncio
                    # https://github.com/python/asyncio/issues/488
                    if str(exc) == "Cannot pause_reading() when closing":
                        raise asyncio.TimeoutError("Request timed out (Got %s: %s)" % (exc.__class__.__name__, exc)) from None
                    else:
                        raise exc from None
            # Some centers do not handle motocycle for example
            elif resp.status == 400:
                payload = await resp.json()
                assert payload["code"] == "1" and payload["type"] == "TECHNICAL", "API responded with 400 code but it is not the usual error: %s" % payload
                payload = {}
            else:
                assert False, "API responded with unexpected %d code: %.80s" % (resp.status, await resp.text())
        except (asyncio.TimeoutError, AssertionError) as exc:
            self.logger.error("Got exception while calling: %s: %s: %s", url, exc.__class__.__name__, exc)
            return None, exc
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception("Got exception while calling: %s: %s: %s", url, exc.__class__.__name__, exc)
            return None, exc
        else:
            return payload, None

    async def refresh_sites(self):
        """ Refresh sites list """

        def fixed(name):
            """
            Attempt to normalize sites names for easier use in URL placeholders
            """

            name = name.replace("/", " sur ")
            name = name.replace(" ", "_")
            return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()

        payload, exc = await self._request(self.site_list_url)

        if exc is not None:
            self.site_handler(None, exc)  # pylint: disable=not-callable
            return

        try:
            organism = "snct"
            sites = {(organism, fixed(x["name"].lower())): x["id"] for x in payload}
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception("Got exception while formatting site payload: %s: %s", exc.__class__.__name__, exc)
            self.site_handler(None, exc)  # pylint: disable=not-callable
        else:
            self.site_list = sites
            self.logger.info("Following sites will be sent to handler: %s", sites)
            self.site_handler(sites, exc)  # pylint: disable=not-callable

    async def refresh_vehicles(self):
        """ Refresh vehicles list """

        def fixed(name):
            """
            Attempt to normalize vehicules types
            Useless at the moment but can help to support Dekra for example
            """

            name = name.replace("voiture", "car")
            name = name.replace("tracteur", "tractor")
            name = name.replace("camionnette", "van")
            name = name.replace("camion", "truck")
            name = name.replace("remorque", "trailer")
            name = name.replace("autobus / autocar", "bus")
            name = name.replace("trailer < 3,5 t", "small_trailer")
            name = name.replace("trailer > 3,5 t", "large_trailer")
            name = name.replace(" ", "_")
            return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()

        payload, exc = await self._request(self.vehicle_list_url)
        if exc is not None:
            self.vehicle_handler(payload, exc)  # pylint: disable=not-callable
            return

        try:
            vehicles = {fixed(x["name"].lower()): x["id"] for x in payload}
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception("Got exception while formatting vehicle payload: %s: %s", exc.__class__.__name__, exc)
            self.vehicle_handler(None, exc)  # pylint: disable=not-callable
        else:
            self.vehicle_list = vehicles
            self.logger.info("Following vehicles will be sent to handler: %s", vehicles)
            self.vehicle_handler(vehicles, exc)  # pylint: disable=not-callable

    async def refresh_appointments(self):  # pylint: disable=too-many-locals
        """ Refresh appointments list """

        inputs = {}
        appointments = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list))))
        count = 0

        for request_type in ["PRIVATE", "PROFESSIONAL"]:
            for control_type in ["REGULAR", "REJECTED"]:
                for vehicule_type, vehicule_type_id in self.vehicle_list.items():
                    for site, site_id in self.site_list.items():
                        url = self.vehicle_appointment_url_template.format(
                            start_dt=self.today_lux_date, end_dt=self.two_month_later_lux_date, vehicle_type=vehicule_type_id, site_id=site_id, request_type=request_type, control_type=control_type
                        )
                        inputs[(request_type, control_type, vehicule_type, site, url)] = None

        # Concurrency limited by asyncio session parameters
        results = await asyncio.gather(*[self._request(x[4]) for x in inputs])

        for inp, result in zip(inputs, results):

            if isinstance(result, Exception):
                self.logger.error("Got exception when querying (1) %s: %s: %s", url, inp.__class__.__name__, inp[4])
                appointments[inp[0]][inp[1]][inp[2]][inp[3]] = None
                continue

            payload, exc = result

            if exc is not None:
                self.logger.error("Got exception when querying (2) %s: %s: %s", url, exc.__class__.__name__, exc)
                appointments[inp[0]][inp[1]][inp[2]][inp[3]] = None
                continue

            self.logger.debug("Refreshing available appointments at %s worked !", inp[4])

            try:
                for time in payload:
                    for date in payload[time]:
                        date_time_str = "%sT%s" % (date, time)
                        date_time_dt = datetime.datetime.strptime(date_time_str, "%Y-%m-%dT%HH%M")
                        appointments[inp[0]][inp[1]][inp[2]][inp[3]].append(date_time_dt)
                        count += 1
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.exception("Got exception while formatting vehicle payload: %s: %s", exc.__class__.__name__, exc)

        self.logger.info("%d appointments will be sent to handler", count)
        self.appointment_handler(appointments)  # pylint: disable=not-callable

    async def refresh_appointments_every_minutes(self):  # pylint: disable=invalid-name
        """ Call refresh_appointments and sleep for 1 minute before doing it again """

        while not self.closed:

            try:
                await self.refresh_appointments()
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.exception("Got exception periodically refreshing appointments: %s: %s", exc.__class__.__name__, exc)
            finally:
                self.logger.info("Sleeping 60s before refreshing again")
                await asyncio.sleep(60)


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
    LOGGER = logging.getLogger(__name__)

    async def test_scrapper():
        """ Run scrapping methods against SNCT website """

        client = SnctAppointmentScrapper()

        try:
            await client.refresh_sites()
            await client.refresh_vehicles()
            await client.refresh_appointments_every_minutes()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("%s: %s", exc.__class__.__name__, exc)
        finally:
            await client.close()

    LOOP = asyncio.get_event_loop()
    TASK = asyncio.ensure_future(test_scrapper())
    try:
        LOOP.run_until_complete(TASK)
    except KeyboardInterrupt:
        LOOP.run_until_complete(TASK)
    finally:
        LOOP.close()
