"""
Return list of organisms and sites
"""


# pylint: disable=line-too-long


import logging
import collections
import aiohttp.web


class RestSites:  # pylint: disable=too-few-public-methods
    """
    Return list of organisms and sites
    """

    logger = logging.getLogger(__name__)

    @classmethod
    async def get(cls, request):
        """
        ---
        description: Return list of organisms and site
        produces:
        - application/json
        tags:
        - definitions
        responses:
          200:
            description: List of organisms and site returned
            schema:
              title: List of_organism_site
              type: object
              example:
                snct:
                  - esch_sur_alzette
                  - sandweiler
                  - wilwerwiltz
                  - livange
                  - bissen
              description: Organism
              additionalProperties:
                type: array
                items:
                  type: string
                  example: esch_sur_alzette
        """

        # Dispatcher service
        disp = request.app["apptm_disp"]

        payload = collections.defaultdict(list)
        for organism, site in disp.sites:
            payload[organism].append(site)

        return aiohttp.web.json_response(payload, status=200)
