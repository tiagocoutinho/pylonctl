import click

from limatb.cli import camera, url, table_style, max_width

from ..camera import Camera, Configuration, camera_table
from .camera import Interface


@camera(name="pylon")
@click.option("--host", type=str, default=None)
@click.option("--model", type=str, default=None)
@click.option("--serial", type=str, default=None)
@click.option("--user-name", type=str, default=None)
@click.option("--packet-size", default=Configuration.packet_size)
@click.option("--inter-packet-delay", default=Configuration.inter_packet_delay)
@click.option("--frame-transmission-delay", default=Configuration.frame_transmission_delay)
@click.option("--output-queue-size", default=Configuration.output_queue_size)
def pylon(
    host, model, serial, user_name,
    packet_size,
    inter_packet_delay,
    frame_transmission_delay,
    output_queue_size
):
    """basler (python) detector specific commands"""
    if url is None:
        return
    if host is not None:
        camera = Camera.from_host(host)
    elif model is not None:
        camera = Camera.from_model(model)
    elif serial is not None:
        camera = Camera.from_serial_number(serial)
    elif user_name is not None:
        camera = Camera.from_user_name(user_name)
    else:
        click.echo("Must give either host, model, serial or user-name", err=True)
        exit(2)
    config = Configuration()
    config.packet_size = packet_size
    config.inter_packet_delay = inter_packet_delay
    config.frame_transmission_delay = frame_transmission_delay
    config.output_queue_size = output_queue_size
    camera.register_configuration(config)

    interface = Interface(camera)
    return interface


def scan(timeout=None):
    return camera_table()


@pylon.command("scan")
@table_style
@max_width
def pylon_scan(table_style, max_width):
    """show accessible basler detectors on the network"""
    table = scan()
    style = getattr(table, "STYLE_" + table_style.upper())
    table.set_style(style)
    table.max_table_width = max_width
    click.echo(table)
