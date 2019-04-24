#!/usr/bin/python3


# pylint: disable=line-too-long


"""
Main file to run Bosch Dome RCP+ PTZ API
"""


import sys
import os
import shutil
import logging
import argparse
import aiohttp.web
import setproctitle

from api_factory import ApiFactory


PROJECT_ROOT = os.path.abspath(os.path.join(__file__, os.pardir))


def set_process_name(config_obj=None):
    """ Set process name according to pom.xml file """

    artifact_id = "bosch-dome-rcpplus-ptz-api"
    version = "1.0"

    # Strip passwords from arguments
    cli_args = " ".join(sys.argv[1:])
    if isinstance(config_obj, argparse.Namespace):
        for key, val in config_obj.__dict__.items():
            if isinstance(val, str) and key.lower().endswith(("pass", "password", "passwd", "key")):
                cli_args = cli_args.replace(val, "<hidden>")

    setproctitle.setproctitle("%s-%s %s" % (artifact_id, version, cli_args))  # pylint: disable=maybe-no-member,bad-option-value,c-extension-no-member


def configure_root_logger(level=logging.INFO):
    """ Override root logger to use a better formatter """

    if os.getenv("NO_LOGS_TS", None) is None:
        formatter = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    else:
        formatter = "%(levelname)-8s [%(name)s] %(message)s"

    logging.basicConfig(level=level, format=formatter, stream=sys.stdout)


def get_arguments_from_cmd_line():
    """ Handle command line arguments """
    # pylint: disable=bad-whitespace

    # Raise terminal size, See https://bugs.python.org/issue13041
    os.environ["COLUMNS"] = str(shutil.get_terminal_size().columns)

    parser = argparse.ArgumentParser(description="Bosch Dome RCP+ PTZ API", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-b", "--bind-address", type=str, default="0.0.0.0", help="Address to bind on", metavar="::1")
    parser.add_argument("-p", "--bind-port", type=int, default=5000, help="Port to bind on", metavar=8877)

    parser.add_argument("-c", "--context-path", type=str, default="/", help="Text to be used as prefix URL")
    parser.add_argument("-d", "--debug", action="store_true", help="Put loggers in DEBUG level")
    parser.add_argument("-o", "--allow-origin", type=str, help="Allow to restrict the API access to the given URL or domain only")

    parser.add_argument("-s", "--swagger-ui-schemes", type=str, nargs="+", default=("http", "https"), help="Override SwaggerUI list of schemes")

    parsed = parser.parse_args()
    if parsed.context_path != "/":
        parsed.context_path = "/" + parsed.context_path.strip("/") + "/"

    parsed.PROJECT_ROOT = PROJECT_ROOT

    return parsed


def create_api():
    """ Setup app for both command line and Gunicorn run """

    config = get_arguments_from_cmd_line()
    log_level = logging.DEBUG if config.debug else logging.INFO
    configure_root_logger(level=log_level)
    set_process_name(config_obj=config)
    return ApiFactory(config=config)


if __name__ == "__main__":

    API = create_api()
    aiohttp.web.run_app(
        API.app, host=API.config.bind_address, port=API.config.bind_port, access_log_format="%s %r [status:%s request:%Tfs bytes:%bb]"
    )
