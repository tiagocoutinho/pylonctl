# pylonctl

Control basler cameras from de command line.

Can also be used as a python library. Components include helpers
to control image acquisition and a library of PyQt widgets.

## Installation

### Linux pre-requisite

pylonctl has a dependency on official pylon python wrapper:
the excelent [pypylon](http://github/basler/pypylon).

At the time of writing this documentation, pypylon is only
available on [Pypi](https://pypi.org/) for Windows.

You can, however download the latest wheel for Linux directly from
the [pypylon github repo](https://github.com/basler/pypylon/releases).
Just download the wheel that is most appropriate to your machine and,
from within your favorite python environment type:

`pip install <wheel file>`

(ex: `pip install pypylon-1.5.4-cp37-cp37m-linux_x86_64.whl`)


Finally, from within your favorite python environment:

`pip install pylonctl`

## Usage

```console
$ pylonctl --help
Usage: pylonctl [OPTIONS] COMMAND [ARGS]...

Options:
  --log-level [debug|info|warning|error]
  --help                          Show this message and exit.

Commands:
  camera     camera related commands
  table      list of available cameras
  transport  transport related commands
```

### List of transports

```console
$ pylonctl transport table
+--------------+------------------+---------------------------------+------------------+
| DeviceClass  |   FriendlyName   |            FullName             |    VendorName    |
+--------------+------------------+---------------------------------+------------------+
|  BaslerUsb   |       USB        |    USB/BaslerUsb 5.2.0.13457    |      Basler      |
+--------------+------------------+---------------------------------+------------------+
|  BaslerGigE  |       GigE       |   GigE/BaslerGigE 5.2.0.13457   |      Basler      |
+--------------+------------------+---------------------------------+------------------+
| BaslerCamEmu | Camera Emulation | CamEmu/BaslerCamEmu 5.2.0.13457 | Camera Emulation |
+--------------+------------------+---------------------------------+------------------+
```

### List of cameras

```console
$ pylonctl table
+-----------------------+-----------------+-----------+---------------------------------+------------------------------+--------------+------------+--------------+
|       FullName        | UserDefinedName | ModelName |          DeviceFactory          |         FriendlyName         | DeviceClass  | VendorName | SerialNumber |
+-----------------------+-----------------+-----------+---------------------------------+------------------------------+--------------+------------+--------------+
| Emulation (0815-0000) |                 | Emulation | CamEmu/BaslerCamEmu 5.2.0.13457 | Basler Emulation (0815-0000) | BaslerCamEmu |   Basler   |  0815-0000   |
+-----------------------+-----------------+-----------+---------------------------------+------------------------------+--------------+------------+--------------+
| Emulation (0815-0001) |                 | Emulation | CamEmu/BaslerCamEmu 5.2.0.13457 | Basler Emulation (0815-0001) | BaslerCamEmu |   Basler   |  0815-0001   |
+-----------------------+-----------------+-----------+---------------------------------+------------------------------+--------------+------------+--------------+
| Emulation (0815-0002) |                 | Emulation | CamEmu/BaslerCamEmu 5.2.0.13457 | Basler Emulation (0815-0002) | BaslerCamEmu |   Basler   |  0815-0002   |
+-----------------------+-----------------+-----------+---------------------------------+------------------------------+--------------+------------+--------------+
| Emulation (0815-0003) |                 | Emulation | CamEmu/BaslerCamEmu 5.2.0.13457 | Basler Emulation (0815-0003) | BaslerCamEmu |   Basler   |  0815-0003   |
+-----------------------+-----------------+-----------+---------------------------------+------------------------------+--------------+------------+--------------+
```

### camera information

```console
$ pylonctl camera --host=10.20.30.40 info
Address: 10.20.30.40:3956
DefaultGateway: 10.20.30.254
DeviceClass: BaslerGigE
DeviceFactory: GigE/BaslerGigE 5.2.0.45678
DeviceVersion: 104845-21
FriendlyName: hpcal (2210004)
FullName: Basler acA1300-30gm#004050607080#10.20.30.40:3956
Interface: 10.20.30.1
IpAddress: 10.20.30.40
IpConfigCurrent: 6
IpConfigOptions: 7
MacAddress: 004050607080
ModelName: acA1300-30gm
PortNr: 3956
SerialNumber: 2210004
SubnetAddress: 10.20.30.255
SubnetMask: 255.255.255.0
UserDefinedName: hpcal
VendorName: Basler
XMLSource: Device
```

### camera parameters

```console
$ pylonctl camera --model=Emulation param tree
Root
├── AOI
│   ├── Height
│   │   ├── limits: (1, 4096)
│   │   ├── readonly: False
│   │   ├── step: 1
│   │   ├── suffix:
│   │   ├── tip: Sets the height of the area of interest in pixels.
│   │   ├── title: Height
│   │   ├── type: int
│   │   └── value: 1040
│   ├── HeightMax
│   │   ├── limits: (1040, 32768)
│   │   ├── readonly: False
│   │   ├── step: 1
│   │   ├── suffix:
│   │   ├── tip: Indicates the maximum allowed height of the image in pixels.
│   │   ├── title: Max Height
│   │   ├── type: int
│   │   └── value: 4096
│   ├── OffsetX
│   │   ├── limits: (0, 3072)
│   │   ├── readonly: False
│   │   ├── step: 1
│   │   ├── suffix:
│   │   ├── tip: Sets the X offset (left offset) of the area of interest in pixels.
│   │   ├── title: X Offset
│   │   ├── type: int
│   │   └── value: 0
...
├── TransportLayer
│   ├── ForceFailedBuffer
│   │   ├── readonly: False
│   │   ├── tip: Marks the next buffer as failed.
│   │   ├── title: Force Failed Buffer
│   │   └── type: action
│   ├── ForceFailedBufferCount
│   │   ├── limits: (1, 1024)
│   │   ├── readonly: False
│   │   ├── step: 1
│   │   ├── suffix:
│   │   ├── tip: Number of failed buffers to generate.
│   │   ├── title: Failed Buffer Count
│   │   ├── type: int
│   │   └── value: 100
│   ├── PayloadSize
│   │   ├── limits: (-9223372036854775808, 9223372036854775807)
│   │   ├── readonly: True
│   │   ├── step: 1
│   │   ├── suffix:
│   │   ├── tip: Size of the payload in bytes.
│   │   ├── title: PayloadSize
│   │   ├── type: int
│   │   └── value: 1064960
│   ├── readonly: True
│   ├── tip: This category includes items related to the IIDC 1394 transport specif[...]
│   ├── title: Transport Layer
│   └── type: group
├── readonly: True
├── title: Root
└── type: group
```

```console
$ pylonctl camera --model=Emulation param tree
+------------------------------------------+------------------+--------+--------+
|                   Name                   |      Value       |  Type  | Access |
+------------------------------------------+------------------+--------+--------+
|                   AOI                    |       None       | group  |   RO   |
+------------------------------------------+------------------+--------+--------+
|         AcquisitionFrameRateAbs          |       10.0       | float  |   RW   |
+------------------------------------------+------------------+--------+--------+
...
+------------------------------------------+------------------+--------+--------+
|             UserSetSelector              |       None       |  list  |   RW   |
+------------------------------------------+------------------+--------+--------+
|                  Width                   |       1024       |  int   |   RW   |
+------------------------------------------+------------------+--------+--------+
|                 WidthMax                 |       4096       |  int   |   RW   |
+------------------------------------------+------------------+--------+--------+
```


### Acquistion

#### Internal trigger

```console
pylonctl --log-level=debug camera --model=Emulation acquire -n 3 -e .1
Acquiring 3 frames on Basler Emulation (0815-0000) (Total acq. time: 0.300s)
2020-05-04 21:33:30,812 DEBUG MainThread Emulation (0815-0000): OnOpened: Preparing network parameters
2020-05-04 21:33:30,813 DEBUG MainThread Emulation (0815-0000): OnOpened: Finished configuration
2020-05-04 21:33:30,955 INFO MainThread Emulation (0815-0000): Grabbed (1040, 1024) uint8
2020-05-04 21:33:31,067 INFO MainThread Emulation (0815-0000): Grabbed (1040, 1024) uint8
2020-05-04 21:33:31,201 INFO MainThread Emulation (0815-0000): Grabbed (1040, 1024) uint8
Elapsed time: 0.362473s
```

#### Software trigger

```console
pylonctl --log-level=debug camera --model=Emulation acquire -t software -n 3 -e 1
Acquiring 3 frames on Basler Emulation (0815-0000) (Total acq. time: 3.000s)
2020-05-04 21:32:42,855 DEBUG MainThread Emulation (0815-0000): OnOpened: Preparing network parameters
2020-05-04 21:32:42,856 DEBUG MainThread Emulation (0815-0000): OnOpened: Finished configuration
Press any key to trigger acquisition 1 of 3...
2020-05-04 21:32:46,123 INFO MainThread Emulation (0815-0000): Grabbed (1040, 1024) uint8
Press any key to trigger acquisition 2 of 3...
2020-05-04 21:32:47,675 INFO MainThread Emulation (0815-0000): Grabbed (1040, 1024) uint8
Press any key to trigger acquisition 3 of 3...
2020-05-04 21:32:49,312 INFO MainThread Emulation (0815-0000): Grabbed (1040, 1024) uint8
Elapsed time: 6.425155s
```
