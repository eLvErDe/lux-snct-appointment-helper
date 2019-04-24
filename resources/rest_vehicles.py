"""
Return list of vehicle categories
"""


# pylint: disable=line-too-long


import logging
import aiohttp.web


class RestVehicles:  # pylint: disable=too-few-public-methods
    """
    Return list of vehicle categories
    """

    logger = logging.getLogger(__name__)

    @classmethod
    async def get(cls, request):
        """
        ---
        description: Return list of vehicle categories
        produces:
        - application/json
        tags:
        - definitions
        responses:
          200:
            description: List of vehicle categories returned
            schema:
              title: List of_vehicle_categories
              type: array
              example:
                - large_trailer
                - truck
                - motocycle
                - tractor
                - van
                - small_trailer
                - bus
                - car
              items:
                type: string
                example: car
        """

        # Dispatcher service
        disp = request.app["apptm_disp"]

        return aiohttp.web.json_response(list(disp.vehicle_types.keys()), status=200)
