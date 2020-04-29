import fnmatch
import logging

import click

from .tool import Camera
from .tool import obj_tree, obj_table
from .tool import prop_list_table, iacquire, transport_factory


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
    pass


@transport.command("list")
def transport_list():
    tl_list = transport_factory().EnumerateTls()
    width = click.get_terminal_size()[0]
    table = prop_list_table(*tl_list, max_width=width)
    click.echo(table)


@cli.command("list")
def device_list():
    dev_info_list = transport_factory().EnumerateDevices()
    width = click.get_terminal_size()[0]    
    table = prop_list_table(*dev_info_list, max_width=width)
    click.echo(table)


@cli.group("camera")
@click.option('--host', type=str) 
@click.pass_context
def camera(ctx, host):
    camera = Camera.from_host(host)
    if camera is None:
        print('Could not find camera with IP {!r}'.format(ip))
        click.exit(1)
    ctx.obj['camera'] = camera


@camera.command("info")
@click.pass_context
def info(ctx):
    cam = ctx.obj['camera']
    click.echo('{!r}'.format(cam))


@camera.command("tree")
@click.option('--filter', type=str, default='*')
@click.pass_context
def tree(ctx, filter):
    cam = ctx.obj['camera']
    filt = lambda o: fnmatch.fnmatch(o[0], filter)
    with cam:
        tree = obj_tree(cam, filt=filt)
    click.echo(tree)


@camera.command("table")
@click.option('--filter', type=str, default='*')
@click.pass_context
def table(ctx, filter):
    cam = ctx.obj['camera']
    filt = lambda o: fnmatch.fnmatch(o[0], filter)
    width = click.get_terminal_size()[0]
    with cam:
        table = obj_table(cam, max_width=width, filt=filt)
    click.echo(table)


@camera.command("acquire")
@click.option('-n', '--nb-frames', default=10)
@click.option('-e', '--exposure', default=0.1)
@click.option('-l', '--latency', default=0.)
@click.pass_context
def acquire(ctx, nb_frames, exposure, latency):
    camera = ctx.obj['camera']
    click.echo(f'Acquiring {nb_frames} frames on {camera}')
    with camera:
        for result in iacquire(camera, nb_frames, exposure, latency):
            if result.GrabSucceeded():
                # Access the image data.
                print("SizeX: ", result.Width)
                print("SizeY: ", result.Height)
                img = result.Array
                print(f"buffer shape={img.shape} dtype={img.dtype}")   
            result.Release()


@camera.command("gui")
@click.pass_context
def camera_gui(ctx):
    from .gui import main
    main(ctx.obj['camera'])


if __name__ == "__main__":
    cli(obj={})
