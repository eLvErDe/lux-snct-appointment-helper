#!/usr/bin/python3


# pylint: disable=line-too-long


"""
WS clients for testing purpose
"""


import os
import logging
import asyncio
import datetime
import pytz
import aiohttp


HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 5000))

URL = "http://%s:%s/appointments/ws" % (HOST, PORT)

LOGGER = logging.getLogger("ws_client_test")


async def connect_and_listen(name, criterias):
    """ Connect Websocket, send criteria and wait for responses """

    session = aiohttp.ClientSession()
    websocket = await session.ws_connect(URL)
    LOGGER.info("Client %s connected with criterias: %s", name, criterias)

    await websocket.send_json(criterias)

    while True:
        msg = await websocket.receive()
        LOGGER.info("Message received on client %s from server: %s", name, msg)

        if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
            LOGGER.info("Client %s closed", name)
            break


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s")

    LOOP = asyncio.get_event_loop()

    ONE_WEEK_LATER = datetime.datetime.now(tz=pytz.timezone("Europe/Luxembourg")) + datetime.timedelta(days=7)
    TWO_WEEKS_LATER = ONE_WEEK_LATER + datetime.timedelta(days=7)

    CRITERIAS = [
        [
            {
                "start_dt": ONE_WEEK_LATER.isoformat(),
                "end_dt": TWO_WEEKS_LATER.isoformat(),
                "organism": "snct",
                "site": "sandweiler",
                "user_type": "PRIVATE",
                "control_type": "REGULAR",
                "vehicle_type": "car",
            },
            {
                "start_dt": ONE_WEEK_LATER.isoformat(),
                "end_dt": TWO_WEEKS_LATER.isoformat(),
                "organism": "snct",
                "site": "esch_sur_alzette",
                "user_type": "PRIVATE",
                "control_type": "REGULAR",
                "vehicle_type": "car",
            },
        ],
        [
            {
                "start_dt": ONE_WEEK_LATER.isoformat(),
                "end_dt": TWO_WEEKS_LATER.isoformat(),
                "organism": "snct",
                "site": "esch_sur_alzette",
                "user_type": "PRIVATE",
                "control_type": "REGULAR",
                "vehicle_type": "car",
            }
        ],
        [
            {
                "start_dt": ONE_WEEK_LATER.isoformat(),
                "end_dt": TWO_WEEKS_LATER.isoformat(),
                "organism": "snct",
                "site": "livange",
                "user_type": "PROFESSIONAL",
                "control_type": "REGULAR",
                "vehicle_type": "bus",
            }
        ],
    ]

    LOOP.run_until_complete(
        asyncio.gather(
            asyncio.ensure_future(connect_and_listen("car-esch/sandweiler", CRITERIAS[0])),
            asyncio.ensure_future(connect_and_listen("car-esch", CRITERIAS[1])),
            asyncio.ensure_future(connect_and_listen("bus-livange", CRITERIAS[2])),
        )
    )
