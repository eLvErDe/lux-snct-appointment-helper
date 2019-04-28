"""
WebSocket API:
  * Client send criteria of interrest
  * Appointment dispatcher send appointments matching criteria
"""


# pylint: disable=line-too-long


import asyncio
import logging
import datetime
import functools
import json
import aiohttp
import dateutil.parser


class WsAppointments:  # pylint: disable=invalid-name,too-few-public-methods
    """
    WebSocket API:
      * Client send criteria of interrest
      * Appointment dispatcher send appointments matching criteria
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get(self, request):
        """
        ---
        description: |
                     ## THIS IS A WEBSOCKET ROUTE

                     * body is the type of message you need to send as subscription criterias
                     * 101 response is defining the type of messages you will receive
        produces:
        - application/json
        tags:
        - appointments
        parameters:
        - in: body
          name: criterias_list
          description: List of criterias to filter appointments (publish to WS after connecting)
          type: array
          items:
            type: object
            required:
              - user_type
              - control_type
              - vehicle_type
              - organism
              - site
              - start_date
              - end_date
            properties:
              start_date:
                description: Seek for appointment after this date (included)
                type: string
                format: date
                required: true
              end_date:
                description: Seek for appointment before this date (excluded)
                type: string
                format: date
                required: true
              user_type:
                description: Type of user (private or pro)
                type: string
                enum: ["PRIVATE", "PROFESSIONAL"]
                default: PRIVATE
              control_type:
                description: Type of control (initial or re-test for a rejected vehicule)
                type: string
                enum: ["REGULAR", "REJECT"]
                default: REGULAR
              vehicle_type:
                description: Type of vehicle
                type: string
                enum: ["motocycle", "car", "bus", "small_trailer", "large_trailer", "van", "truck", "tractor"]
                default: car
              organism:
                description: SNCT or a private competitor
                type: string
                enum: ["snct"]
                default: snct
              site:
                description: Site name, like esch_sur_alzette for SNCT
                type: string
        responses:
          101:
            description: Subcribed to new appointments successfully
            schema:
              title: List of_appointments
              type: array
              items:
                type: object
                required:
                  - user_type
                  - control_type
                  - vehicle_type
                  - organism
                  - site
                  - timestamp
                properties:
                  user_type:
                    description: Type of user (private or pro)
                    type: string
                    enum: ["PRIVATE", "PROFESSIONAL"]
                    default: PRIVATE
                  control_type:
                    description: Type of control (initial or re-test for a rejected vehicule)
                    type: string
                    enum: ["REGULAR", "REJECT"]
                    default: REGULAR
                  vehicle_type:
                    description: Type of vehicle
                    type: string
                    enum: ["motocycle", "car", "bus", "small_trailer", "large_trailer", "van", "truck", "tractor"]
                    default: car
                  organism:
                    description: SNCT or a private competitor
                    type: string
                    enum: ["snct"]
                    default: snct
                  site:
                    description: Site name, like esch_sur_alzette for SNCT
                    type: string
                  timestamp:
                    description: Date and time of the available appointment slot
                    type: string
                    format: date-time
          400:
            description: Bad request
            schema:
              title: Bad_Request
              type: object
              required:
                - status
                - message
              properties:
                message:
                  type: string
                  description: Validation error message
                  example: "control_type must be one of: private, pro"
                status:
                  type: number
                  description: HTTP error status code
                  example: 400
          403:
            description: Forbidden
            schema:
              title: Forbidden
              type: object
              required:
                - status
                - message
              properties:
                message:
                  type: string
                  description: You are doing classic HTTP on a Websocket route
                  example: This route is for WebSocket clients only
                status:
                  type: number
                  description: HTTP error status code
                  example: 403
        """

        self.logger.info("New client subscribed to appointments WS stream")
        ws_handler = WsHandler(self, request, asyncio.Task.current_task())
        await ws_handler.prepare()
        ws_obj = await ws_handler.run_forever()
        return ws_obj


class WsHandler:
    """
    Handle a ws_obj
    """

    def __init__(self, factory, request, aiohttp_task):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.factory = factory
        self.request = request
        self.aiohttp_task = aiohttp_task
        self.ws = aiohttp.web.WebSocketResponse()  # pylint: disable=invalid-name

    @property
    def app(self):
        """ Return aiohttp App from request """

        return self.request.app

    @property
    def disp(self):
        """ Return AppointmentDispatcher instance from app """

        return self.app["apptm_disp"]

    @staticmethod
    def json_serializer(payload):
        """ A serializer handling datetime.datetime to iso8601 """

        if isinstance(payload, datetime.datetime):
            return payload.isoformat()
        return payload

    def add_to_ws_stream_coro(self):
        """
        Add this handler coroutine to an aiohttp server service
        so it can be stopped on server shutdown
        """

        self.app["ws_stream_coro"].add(self.aiohttp_task)

    def remove_from_ws_stream_coro(self):
        """
        Remove this handler coroutine from aiohttp server service
        because it has been stopped client side
        """

        try:
            self.app["ws_stream_coro"].remove(self.aiohttp_task)
        except KeyError:
            pass

    async def prepare(self):
        """ Prepare WebSocket response """

        await self.ws.prepare(self.request)
        self.add_to_ws_stream_coro()
        self.logger.info("Client connected")

    async def send_json(self, payload):
        """ Send a JSON to WebSocket client """

        await self.ws.send_json(payload, dumps=functools.partial(json.dumps, default=self.json_serializer))

    async def close(self):
        """ Close WebSocket object """

        await self.ws.close()
        self.remove_from_ws_stream_coro()
        self.disp.unregister_appointment_client(self)
        self.logger.info("Client disconnected")

    def validate_criterias(self, criterias):
        """
        Validate appoitments criteria received on Websocket
        """

        criterias = json.loads(criterias)
        assert isinstance(criterias, list), "criterias must be a list of dict"

        for criteria in criterias:

            user_type = criteria.get("user_type", None)
            control_type = criteria.get("control_type", None)
            vehicle_type = criteria.get("vehicle_type", None)
            organism = criteria.get("organism", None)
            site = criteria.get("site", None)
            start_dt = criteria.get("start_dt", None)
            end_dt = criteria.get("end_dt", None)

            assert user_type in ["PRIVATE", "PROFESSIONAL"], "user_type must be one of PRIVATE, PROFESSIONAL"
            assert control_type in ["REGULAR", "REJECTED"], "user_type must be one of REGULAR, REJECTED"
            assert vehicle_type in self.disp.appointments[user_type][control_type].keys(), "vehicle_type must be one of %s" % list(
                self.disp.appointments[user_type][control_type].keys()
            )
            assert organism in ["snct"], "user_type must be one of snct"
            organism_site = (organism, site)
            assert organism_site in self.disp.appointments[user_type][control_type][vehicle_type].keys(), "site must be one of %s" % list(
                self.disp.appointments[user_type][control_type][vehicle_type].keys()
            )
            try:
                start_dt = dateutil.parser.parse(start_dt)
                criteria["start_dt"] = start_dt
            except:  # pylint: disable=broad-except
                raise AssertionError("start_dt must be a date like 2019-01-01 or a datetime like 2019-01-01T08:15:00")
            try:
                end_dt = dateutil.parser.parse(end_dt)
                criteria["end_dt"] = end_dt
            except:  # pylint: disable=broad-except
                raise AssertionError("end_date must be a date like 2019-02-01 or a datetime like 2019-01-01T09:30:00")

            return criterias

    async def push_appointments(self, appointments):
        """
        Method called by AppointmentDispatcher when new appointments
        match giver criterias
        """

        await self.send_json({"appointments": appointments})

    async def run_forever(self):  # pylint: disable=too-many-branches
        """
        Run WebSocket until it's stopped either by server or by client
        Also send an error JSON if receiving something
        """

        try:  # pylint: disable=too-many-nested-blocks
            while not self.ws.closed:
                msg = await self.ws.receive()
                if msg.tp == aiohttp.WSMsgType.text:
                    if msg.data == "close":
                        break
                    else:
                        try:
                            criterias = self.validate_criterias(msg.data)
                        except AssertionError as exc:
                            await self.send_json({"message": str(exc), "status": 400})
                        except Exception as exc:  # pylint: disable=broad-except
                            await self.send_json({"message": "Got unhandled type of message", "status": 500})
                            self.logger.warning("Got invalid WebSocket payload: %s: %s: %s", exc.__class__.__name__, exc, msg.data)
                        else:
                            self.logger.info("Got valid criterias: %s", criterias)
                            self.disp.register_appointment_client(self, criterias)
                elif msg.tp == aiohttp.WSMsgType.close:
                    break
                # aiohttp.WSMsgType.closing existence seems to depends on aiohttp version
                elif hasattr(aiohttp.WSMsgType, "closing") and msg.tp == aiohttp.WSMsgType.closing:  # pylint: disable=no-member
                    break
                else:
                    self.logger.warning("Client sent an unknown message: %s", msg)
            return self.ws
        except asyncio.CancelledError:
            return self.ws
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception("Exception in WsHandler: %s: %s", exc.__class__.__name__, exc)
            return self.ws
        finally:
            # In case of CancelledError, client does not close properly but crash
            # This is why we have to use asycio.shield
            try:
                await asyncio.shield(self.close())
            except asyncio.CancelledError:
                pass
