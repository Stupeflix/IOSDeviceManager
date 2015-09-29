import posixpath
import stat

class Manager(object):
    def __init__(self, bundle_name, device_id):
        from MobileDevice import afcapplicationdirectory
        # Important : convert to unicode, or nothing will work
        self.bundle_name = unicode(bundle_name)
        self.device_id = device_id

        # If no device id is given, only usb attached devices are considered
        if self.device_id == None:
            usb_only = True
        else:
            usb_only = False

        devices = self.list_devices(usb_only = usb_only)

        if usb_only:
            if len(devices) == 0:
                raise Exception("No USB attached device was found")

        self.device = None
        for info in devices:
            name = info["id"]
            if name == self.device_id or self.device_id == None:
                self.device = info["device"]
                break

        if self.device == None:
            raise Exception("Device %s was not found" % self.device_id)

        self.device.connect(False)

        self.afc = afcapplicationdirectory.AFCApplicationDirectory(self.device, self.bundle_name)

    @classmethod
    def list_devices(self, usb_only = True, full_info = False):
        from MobileDevice import list_devices as md_list_devices
        from MobileDevice import AMDevice

        raw_devices = md_list_devices()
        devices = []
        for r,s in raw_devices.iteritems():
            if usb_only:
                if s.get_interface_type() != AMDevice.INTERFACE_USB:
                    continue

            info = {"id":r, "device":s}

            if full_info:
                try:
                    s.connect(False)
                    for key in ["ProductVersion", "BuildVersion", "DeviceName"]:
                        info[key] = s.get_value(name=unicode(key))
                except:
                    print "Warning: Could not connect to device to retrieve full information. device id: %s" % r
                    continue
                finally:
                    s.disconnect()

            devices += [info]



        return devices

    def enumerate_ios_dir(self, path = "/", file_only = False):
        for name in self.afc.listdir(path):
            full_path = posixpath.join(path, name)
            info = self.afc.lstat(full_path)
            if info.st_ifmt != stat.S_IFREG:
                if not file_only:
                    yield full_path
                self.enumerate_ios_dir(full_path, file_only = file_only)
            else:
                yield full_path
