"""
Return available appointments for given filter
"""


# pylint: disable=line-too-long


import logging
import datetime
import aiohttp.web


class RestAppointments:  # pylint: disable=too-few-public-methods
    """
    Return available appointments for given filter
    """

    logger = logging.getLogger(__name__)

    @classmethod
    async def get(cls, request):
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
          enum: ["PRIVATE", "PROFESSIONAL"]
          default: PRIVATE
          required: true
        - in: path
          name: control_type
          description: Type of control (initial or re-test for a rejected vehicule)
          type: string
          enum: ["REGULAR", "REJECT"]
          default: REGULAR
          required: true
        - in: path
          name: vehicle_type
          description: Type of vehicle
          type: string
          enum: ["motocycle", "car", "bus", "small_trailer", "large_trailer", "van", "truck", "tractor"]
          default: car
          required: true
        - in: path
          name: organism
          description: SNCT or a private competitor
          type: string
          enum: ["snct"]
          default: snct
          required: true
        - in: path
          name: site
          description: Site name, like esch_sur_alzette for SNCT
          type: string
          required: true
        - in: path
          name: start_date
          description: Seek for appointment after this date (included)
          type: string
          format: date
          required: true
        - in: path
          name: end_date
          description: Seek for appointment before this date (excluded)
          type: string
          format: date
          required: true
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
                  example: "control_type must be one of: PRIVATE, PROFESSIONAL"
                status:
                  type: integer
                  description: HTTP error status code
                  example: 400
        """

        # Path fragments
        user_type = request.match_info["user_type"]
        control_type = request.match_info["control_type"]
        vehicle_type = request.match_info["vehicle_type"]
        organism = request.match_info["organism"]
        site = request.match_info["site"]
        start_date = request.match_info["start_date"]
        end_date = request.match_info["end_date"]

        # Dispatcher service having all appointments
        disp = request.app["apptm_disp"]

        assert user_type in ["PRIVATE", "PROFESSIONAL"], "user_type must be one of PRIVATE, PROFESSIONAL"
        assert control_type in ["REGULAR", "REJECTED"], "user_type must be one of REGULAR, REJECTED"
        assert vehicle_type in disp.appointments[user_type][control_type].keys(), "vehicle_type must be one of %s" % list(disp.appointments[user_type][control_type].keys())
        assert organism in ["snct"], "user_type must be one of snct"
        assert (organism, site) in disp.appointments[user_type][control_type][vehicle_type].keys(), "site must be one of %s" % list(disp.appointments[user_type][control_type][vehicle_type].keys())
        try:
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        except:  # pylint: disable=broad-except
            raise AssertionError("start_date must be a date like 2019-01-01")
        try:
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except:  # pylint: disable=broad-except
            raise AssertionError("end_date must be a date like 2019-02-01")

        appointments = disp.appointments[user_type][control_type][vehicle_type][(organism, site)]

        payload = [x.isoformat() for x in sorted(appointments) if start_date >= x < end_date]
        return aiohttp.web.json_response(payload, status=200)
