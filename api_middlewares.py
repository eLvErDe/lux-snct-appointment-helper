""" aiohttp middlewares """


import logging
import functools
import aiohttp


async def rest_error_middleware(_, handler, logger=None):
    """
    A middleware to return rest JSON error when something goes wrong
    Also turn AssertionError into 400 bad request
    """

    async def return_rest_error_response(request, logger=None):
        """ middleware handler """

        try:
            response = await handler(request)

        except Exception as exc:  # pylint: disable=broad-except

            log_level = logging.ERROR
            with_exception = True

            # Define status code according to exception type
            if isinstance(exc, aiohttp.web_exceptions.HTTPException):
                status = exc.status  # pylint: disable=no-member
                message = exc.reason  # pylint: disable=no-member
                log_level = logging.WARNING
                with_exception = False
            elif isinstance(exc, AssertionError):
                status = 400
                message = str(exc)
                log_level = logging.WARNING
                with_exception = False
            else:
                status = 500
                message = "Internal Server Error"

            # Log exception if have a logger
            if isinstance(logger, logging.Logger):
                logger.log(log_level, "Error handling request: %s: %s" % (exc.__class__.__name__, exc), exc_info=with_exception)

            rest_error = {"message": message, "status": status}
            response = aiohttp.web.json_response(rest_error, status=status)

        finally:
            return response  # pylint: disable=lost-exception

    return functools.partial(return_rest_error_response, logger=logger)
