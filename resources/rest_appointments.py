"""
Return available appointments for given filter
"""


# pylint: disable=line-too-long


import logging
import aiohttp.web


class RestAppointments:  # pylint: disable=too-few-public-methods
    """
    Return available appointments for given filter
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
        parameters:
        - in: path
          name: user_type
          description: Type of user (private or pro)
          type: string
          enum: ["private", "pro"]
        - in: path
          name: control_type
          description: Type of control (initial or re-test for a rejected vehicule)
          type: string
          enum: ["regular", "rejected"]
        - in: path
          name: organism
          description: SNCT or a private concurrent
          type: string
          enum: ["snct"]
        - in: path
          name: site
          description: Site name, like esch_sur_alzette for SNCT
          type: string
        - in: vehicle_type
          name: site
          description: Type of vehicle
          type: string
          enum: ["motocycle", "car", "bus", "small_trailer", "large_trailer", "van", "truck", "tractor"]
        - in: path
          name: start_date
          description: Seek for appointment after this date (included)
          type: string
          format: date
        - in: path
          name: end_date
          description: Seek for appointment before this date (excluded)
          type: string
          format: date
        responses:
          200:
            description: Available appointments slots returned
            schema:
              title: List of_appointments
              type: array
              items:
                type: object
                required:
                  - timestamp
                properties:
                  timestamp:
                    type: string
                    format: date-time
                    description: Date and time of the appointment slot
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
        """

        payload = {"message": "TODO...", "status": 404}
        return aiohttp.web.json_response(payload, status=400)
