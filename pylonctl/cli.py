import fnmatch
import logging

import click
from chronometer import Chronometer

from .camera import (
    Camera,
    Acquisition,
    Configuration,
    ImageLogger,
    parameter_tree,
    parameter_table,
    iter_parameter_display,
    info_table,
    transport_factory,
)


max_width = click.option(
    "--max-width",
    type=int,
    default=lambda: click.get_terminal_size()[0],
    help="maximum table width",
)


style = click.option(
    "--style", type=str, default="default", show_default=True, help="table style"
)


filtering = click.option(
    "--filter",
    type=str,
    default="*",
    show_default=True,
    help="parameter filter (supports pattern matching)",
)


def pause(info="Press any key to continue ...", err=False):
    """Same as click.pause but without masking KeyboardError"""
    if info:
        click.echo(info, nl=False, err=err)
    result = click.getchar()
    if info:
        click.echo(err=err)
    return result


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    default="info",
)
@click.pass_context
def cli(ctx, log_level):
    ctx.ensure_object(dict)
    fmt = "%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"
    logging.basicConfig(level=log_level.upper(), format=fmt)


@cli.group("transport")
def transport():
    """transport related commands"""
    pass


@transport.command("table")
@max_width
@style
def transport_table(max_width, style):
    """list of available transports"""
    tl_list = transport_factory().EnumerateTls()
    table = info_table(*tl_list)
    style = getattr(table, "STYLE_" + style.upper())
    table.max_table_width = max_width
    table.set_style(style)
    click.echo(table)


@cli.command("table")
@max_width
@style
def camera_table(max_width, style):
    """list of available cameras"""
    dev_info_list = transport_factory().EnumerateDevices()
    garbage = {
        "DeviceFactory", "SubnetAddress", "IpConfigOptions", "IpConfigCurrent",
        "DefaultGateway", "SubnetMask"
    }
    table = info_table(*dev_info_list, filt=lambda c: c not in garbage)
    style = getattr(table, "STYLE_" + style.upper())
    table.max_table_width = max_width
    table.set_style(style)
    click.echo(table)


@cli.group("camera")
@click.option("--host", type=str, default=None)
@click.option("--model", type=str, default=None)
@click.option("--serial", type=str, default=None)
@click.option("--user-name", type=str, default=None)
@click.option("--packet-size", default=Configuration.packet_size)
@click.option("--inter-packet-delay", default=Configuration.inter_packet_delay)
@click.option(
    "--frame-transmission-delay", default=Configuration.frame_transmission_delay
)
@click.option("--output-queue-size", default=Configuration.output_queue_size)
@click.pass_context
def camera(
    ctx,
    host,
    model,
    serial,
    user_name,
    packet_size,
    inter_packet_delay,
    frame_transmission_delay,
    output_queue_size,
):
    """camera related commands"""
    if host is not None:
        camera = Camera.from_host(host)
    elif model is not None:
        camera = Camera.from_model(model)
    else:
        click.echo("Must give either host, model, serial or user-name", err=True)
        click.exit(2)
    if camera is None:
        click.echo("Could not find camera", err=True)
        click.exit(1)
    config = Configuration()
    config.packet_size = packet_size
    config.inter_packet_delay = inter_packet_delay
    config.frame_transmission_delay = frame_transmission_delay
    config.output_queue_size = output_queue_size
    camera.register_configuration(config)
    ctx.obj["camera"] = camera
    ctx.obj["config"] = config


@camera.command("info")
@click.pass_context
def camera_info(ctx):
    """camera info (IP, serial number, MAC, etc)"""
    cam = ctx.obj["camera"]
    click.echo("{!r}".format(cam))


@camera.group("param")
def camera_param():
    """camera parameter related commands"""


@camera_param.command("list")
@filtering
@click.pass_context
def camera_param_values(ctx, filter):
    """list of parameter names and values"""
    cam = ctx.obj["camera"]

    def filt(o):
        return fnmatch.fnmatch(o[0], filter)

    with cam:
        for text in iter_parameter_display(cam, filt=filt):
            click.echo(text)


@camera_param.command("tree")
@filtering
@click.pass_context
def camera_param_tree(ctx, filter):
    """display camera parameters in a tree"""
    cam = ctx.obj["camera"]

    def filt(o):
        return fnmatch.fnmatch(o["name"], filter)

    with cam:
        tree = parameter_tree(cam, filt=filt)
    if tree.size():
        click.echo(tree)
    else:
        click.echo("no item matches specified filter", err=True)


@camera_param.command("table")
@filtering
@style
@click.pass_context
def camera_param_table(ctx, filter, style):
    """display list of camera parameters in a table"""
    cam = ctx.obj["camera"]

    def filt(o):
        return fnmatch.fnmatch(o[0], filter)

    with cam:
        table = parameter_table(cam, filt=filt)
    style = getattr(table, "STYLE_" + style.upper())
    table.max_table_width = click.get_terminal_size()[0]
    table.set_style(style)
    click.echo(table)


@camera.command("acquire")
@click.option(
    "-t",
    "--trigger",
    default="internal",
    type=click.Choice(["internal", "software"], case_sensitive=False),
)
@click.option("-n", "--nb-frames", default=10)
@click.option("-e", "--exposure", default=0.1)
@click.option("-l", "--latency", default=0.0)
@click.option("-r", "--roi", default=None, type=str, help="x0,y0,w,h")
@click.option("-b", "--binning", default=None, type=str, help="horiz,vert")
@click.pass_context
def general_acquisition(ctx, trigger, nb_frames, exposure, latency, roi, binning):
    """do an acquisition"""
    camera = ctx.obj["camera"]
    config = ctx.obj["config"]
    trigger = trigger.lower()
    config.trigger_source = trigger
    camera.register_image_event_handler(ImageLogger())
    total_time = nb_frames * (exposure + latency)
    if roi is not None:
        roi = [int(i) for i in roi.split(",")]
        assert len(roi) == 4
    if binning is not None:
        binning = [int(i) for i in binning.split(",")]
        assert len(binning) == 2
    msg = f"Acquiring {nb_frames} frames on {camera}"
    if nb_frames:
        total_time = nb_frames * (exposure + latency)
        msg += f" (Total acq. time: {total_time:.3f}s)"
    click.echo(msg)
    with camera:
        with Acquisition(
            camera, nb_frames, exposure, latency, roi=roi, trigger=trigger
        ) as acq:
            acq.start()
            try:
                with Chronometer() as chrono:
                    frame_nb = 0
                    while frame_nb < nb_frames or not nb_frames:
                        if trigger == "software":
                            pause(
                                "Press any key to trigger acquisition "
                                f"{frame_nb+1} of {nb_frames}... "
                            )
                        result = next(acq)
                        result.Release()
                        frame_nb += 1
            finally:
                click.secho("Elapsed time: {:.6f}s".format(chrono.elapsed))


@camera.group("gui")
@click.pass_context
def camera_gui(ctx):
    """camera GUI related commands"""
    pass


@camera_gui.command("main")
@click.pass_context
def camera_gui_main(ctx):
    """main camera GUI"""
    from .gui.main import main

    main(ctx.obj["camera"])


@camera_gui.command("table")
@click.pass_context
def camera_gui_table(ctx):
    """camera parameter table GUI"""
    from .gui.param import main

    main(ctx.obj["camera"])


if __name__ == "__main__":
    cli(obj={})