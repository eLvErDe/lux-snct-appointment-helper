"""
WebSocket API:
  * Client send criteria of interrest
  * Appointment dispatcher send appointments matching criteria
"""


# pylint: disable=line-too-long


import asyncio
import logging
import aiohttp


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
        description: Return a list of available appointments timeslots
        produces:
        - application/json
        tags:
        - appointments
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
                    description: SNCT or a private concurrent
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
        ws_handler = WsHandler(request, asyncio.Task.current_task())
        await ws_handler.prepare()
        ws_obj = await ws_handler.run_forever()
        return ws_obj


class WsHandler:
    """
    Handle a ws_obj
    """

    def __init__(self, request, aiohttp_task):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.request = request
        self.aiohttp_task = aiohttp_task
        self.ws = aiohttp.web.WebSocketResponse()  # pylint: disable=invalid-name

    @property
    def app(self):
        """ Return aiohttp App from request """

        return self.request.app

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

        await self.ws.send_json(payload)

    async def close(self):
        """ Close WebSocket object """

        await self.ws.close()
        self.remove_from_ws_stream_coro()
        self.logger.info("Client disconnected")

    async def run_forever(self):
        """
        Run WebSocket until it's stopped either by server or by client
        Also send an error JSON if receiving something
        """

        try:
            while not self.ws.closed:
                msg = await self.ws.receive()
                if msg.tp == aiohttp.WSMsgType.text:
                    if msg.data == "close":
                        break
                    else:
                        await self.send_json({"message": "This WS route does not receive messages", "status": 400})
                elif msg.tp == aiohttp.WSMsgType.close:
                    break
                elif msg.tp == aiohttp.WSMsgType.closing:
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
            await asyncio.shield(self.close())
