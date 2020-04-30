import fnmatch
import logging

import click
from chronometer import Chronometer

from .camera import (Camera, Acquisition, parameter_tree, parameter_table,
                     iter_parameter_display, info_table, transport_factory)


max_width = click.option(
    '--max-width', type=int, default=lambda: click.get_terminal_size()[0],
    help='maximum table width')


style = click.option(
    '--style', type=str, default='default', show_default=True,
    help='table style')


filtering = click.option(
    '--filter', type=str, default='*', show_default=True,
    help="parameter filter (supports pattern matching)")


@click.group()
@click.option(
    '--log-level', type=click.Choice(
        ['debug', 'info', 'warning', 'error'], case_sensitive=False),
    default='info')
@click.pass_context
def cli(ctx, log_level):
    ctx.ensure_object(dict)
    fmt = '%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s'
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
    style = getattr(table, 'STYLE_' + style.upper())
    table.max_table_width = max_width
    table.set_style(style)
    click.echo(table)


@cli.command("table")
@max_width
@style
def camera_table(max_width, style):
    """list of available cameras"""
    dev_info_list = transport_factory().EnumerateDevices()
    table = info_table(*dev_info_list)
    style = getattr(table, 'STYLE_' + style.upper())
    table.max_table_width = max_width
    table.set_style(style)
    click.echo(table)


@cli.group("camera")
@click.option('--host', type=str, required=True)
@click.option('--packet-size', default=1500)
@click.option('--inter-packet-delay', default=0)
@click.option('--frame-transmission-delay', default=0)
@click.pass_context
def camera(ctx, host, packet_size, inter_packet_delay, frame_transmission_delay):
    """camera related commands"""
    camera = Camera.from_host(host)
    if camera is None:
        print('Could not find camera with IP {!r}'.format(ip))
        click.exit(1)
    camera.Open()
    camera.GevSCPSPacketSize = packet_size
    camera.GevSCPD = inter_packet_delay
    camera.GevSCFTD = frame_transmission_delay
    ctx.obj['camera'] = camera
    

@camera.command("info")
@click.pass_context
def camera_info(ctx):
    """camera info (IP, serial number, MAC, etc)"""
    cam = ctx.obj['camera']
    click.echo('{!r}'.format(cam))


@camera.group("param")
def camera_param():
    """camera parameter related commands"""

@camera_param.command("list")
@filtering
@click.pass_context
def camera_param_values(ctx, filter):
    """list of parameter names and values""" 
    cam = ctx.obj['camera']
    filt = lambda o: fnmatch.fnmatch(o[0], filter)
    with cam:
        for text in iter_parameter_display(cam, filt=filt):
            click.echo(text)


@camera_param.command("tree")
@filtering
@click.pass_context
def camera_param_tree(ctx, filter):
    """display camera parameters in a tree"""
    cam = ctx.obj['camera']
    filt = lambda o: fnmatch.fnmatch(o['name'], filter)
    with cam:
        tree = parameter_tree(cam, filt=filt)
    if tree.size():
        click.echo(tree)
    else:
        click.echo('no item matches specified filter', err=True)


@camera_param.command("table")
@filtering
@style
@click.pass_context
def table(ctx, filter, style):
    """display list of camera parameters in a table"""
    cam = ctx.obj['camera']
    filt = lambda o: fnmatch.fnmatch(o[0], filter)
    with cam:
        table = parameter_table(cam, filt=filt)
    style = getattr(table, 'STYLE_' + style.upper())
    table.max_table_width = click.get_terminal_size()[0]
    table.set_style(style)
    click.echo(table)


@camera.command("acquire")
@click.option('-n', '--nb-frames', default=10)
@click.option('-e', '--exposure', default=0.1)
@click.option('-l', '--latency', default=0.)
@click.option('--roi', default=None, type=str, help='x0,y0,w,h')
@click.pass_context
def acquire(ctx, nb_frames, exposure, latency, roi):
    """do an acquisition"""
    camera = ctx.obj['camera']
    total_time = nb_frames * (exposure + latency)
    if roi is not None:
        roi = [int(i) for i in roi.split(',')]
        assert len(roi) == 4
    click.echo(f'Acquiring {nb_frames} frames on {camera} (total: {total_time:.3f}s)')
    with camera:
        acq = Acquisition(camera)
        acq.prepare(nb_frames, exposure, latency, roi)
        try:
            with Chronometer() as chrono:
                for i, result in enumerate(acq):
                    if result.GrabSucceeded():
                        data = result.Array
                        click.secho(f'Grabbed #{i} {data.shape} {data.dtype}', fg='green')
                    else:
                        error = result.GetErrorDescription()
                        click.secho('Error: {}'.format(error), fg='red', err=True)
                    result.Release()
        finally:
            click.secho('Elapsed time: {:.6f}s'.format(chrono.elapsed))


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
    main(ctx.obj['camera'])


@camera_gui.command("table")
@click.pass_context
def camera_gui_table(ctx):
    """camera parameter table GUI"""
    from .gui.param import main
    main(ctx.obj['camera'])


if __name__ == "__main__":
    cli(obj={})
