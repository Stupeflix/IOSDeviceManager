import manager
import stat
import os
import traceback
import posixpath

class IOSFile(object):
    def __init__(self, afc, path):
        self.afc = afc
        self.path = path
        self.stat_ = None

    @classmethod
    def create_dest_path(clazz, src_dir, dest_dir, src_file_path):
        src_file_path_rel = src_file_path[len(src_dir):]
        if src_file_path_rel.startswith("/"):
            src_file_path_rel = src_file_path_rel[1:]
        return os.path.join(dest_dir, src_file_path_rel)

    def exists(self):
        try:
            self.stat()
            return True
        except OSError, e:
            print "OSError", e
            return False

    def stat(self):
        if self.stat_ == None:
            self.stat_ = self.afc.lstat(self.path)
        return self.stat_

    def m_time(self):
        return int(self.stat().st_mtime)

    def set_mtime(self, mtime):
        # Not implemented
        pass

    def is_dir(self):
        return self.stat().st_ifmt == stat.S_IFDIR

    def size(self):
        return int(self.stat().st_size)

    def open(self, mode):
        return self.afc.open(self.path, unicode(mode))

    def makedirs(self):
        path = os.path.dirname(self.path)
        dirs_list = [path]
        path_copy = path
        while path_copy != '/' and path_copy:
            path_copy, _ = os.path.split(path_copy)
            dirs_list.append(path_copy)

        dirs_list.reverse()

        for path in dirs_list:
            self.afc.mkdir(path)


class LocalFile(object):
    def __init__(self, afc, path):
        self.path = path
        self.stat_ = None

    @classmethod
    def create_dest_path(clazz, src_dir, dest_dir, src_file_path):
        src_file_path_rel = src_file_path[len(src_dir):]
        if src_file_path_rel.startswith("/"):
            src_file_path_rel = src_file_path_rel[1:]

        ret = os.path.join(dest_dir, src_file_path_rel)
        return ret

    def exists(self):
        return os.path.exists(self.path)

    def stat(self):
        if self.stat_ == None:
            self.stat_ = os.stat(self.path)
        return self.stat_

    def m_time(self):
        return int(self.stat().st_mtime)

    def set_mtime(self, mtime):
        os.utime(self.path, (mtime, mtime))

    def is_dir(self):
        return stat.S_ISDIR(self.stat().st_mode)

    def size(self):
        return self.stat().st_size

    def open(self, mode):
        print "local open", self.path, mode

        return open(self.path, mode + "b")

    def makedirs(self):
        directory = os.path.abspath(os.path.dirname(self.path))
        if os.path.exists(directory):
            if not os.path.isdir(directory):
                os.remove(directory)
                os.makedirs(directory)
        else:
            os.makedirs(directory)

class Syncer(manager.Manager):
    def transfert_file(self, reader, writer, chunk_size = 8192):
        while True:
            data = reader.read(chunk_size)
            if not data:
                break
            writer.write(data)

    def transfert(self, enumerator, src, dest, src_factory, dest_factory):
        afc = self.afc

        # Enumerate source
        for src_path in enumerator:
            # Build dest path
            dest_path = src_factory.create_dest_path(src, dest, src_path)

            src_obj = src_factory(afc, src_path)
            dest_obj = dest_factory(afc, dest_path)

            # By default, does not copy
            copy = False
            # By default, transfert is from the beginning of file
            partial = 0

            # If the destination does not exist, we must obviously transfert it
            if not dest_obj.exists():
                copy = True
            else:
                if src_obj.is_dir() != dest_obj.is_dir():
                    # If type is different, we have a problem ...
                    raise Exception("Type is different : %d, %d for %s, %s", src_obj.is_dir(), dest_obj.is_dir(), src_path, dest_path)
                elif src_obj.m_time() > dest_obj.m_time():
                    # We should copy if times are bad
                    print "Modification time is greater", src_obj.m_time(), dest_obj.m_time()
                    copy = True
                elif src_obj.size() > dest_obj.size():
                    # If size is different, we will resume copying
                    print "Size is different: %s > %s" % (src_obj.size(), dest_obj.size())
                    copy = True
                    partial = dest_obj.size()

            if not copy:
                print "%s : SKIPPING copy to %s" % (src_path, dest_path)
                continue

            # Open input file
            try:
                src_file = src_obj.open(u'rb')
            except: 
                print "Could not open source path: "+src_path
                continue

            # Seek if needed
            if partial != 0:
                src_file.seek(partial)

            # Create destination directory if needed
            dest_obj.makedirs()

            # Open output file
            if partial != 0:
                open_mode = u"a"
            else:
                open_mode = u"w"

            dest_file = dest_obj.open(open_mode)
            if partial != 0:
                print "%s: RESUMING transfer to %s" % (src_path, dest_path)
            else:
                print "%s: COPYING to %s" % (src_path, dest_path)

            # Transfer content
            self.transfert_file(src_file, dest_file)

            # Close everything
            src_file.close()
            dest_file.close()
            dest_obj.set_mtime(src_obj.m_time())

    def enumerate_local_dir(self, path, file_only = False):
        for name in os.listdir(path):
            full_path = posixpath.join(path, name)
            try:
                info = os.stat(full_path)
                if not stat.S_ISREG(info.st_mode):
                    if not file_only:
                        yield full_path
                    self.enumerate_ios_dir(full_path, file_only = file_only)
                else:
                    yield full_path
            except Exception, e:
                print e, traceback.format_exc()


    def download(self, src, dest):
        enumerator = self.enumerate_ios_dir(src, file_only = True)
        self.transfert(enumerator, src, dest, IOSFile, LocalFile)

    def upload(self, src, dest):
        enumerator = self.enumerate_local_dir(src, True)
        self.transfert(enumerator, src, dest, LocalFile, IOSFile)

    def rm_dest(self, dest, recursive=False):
        try:
            self.afc.stat(dest)
        except OSError, e:
            if e.errno == "Unable to open path:":
                return
        self._rm_dir(dest, recursive)

    def _rm_dir(self, dest, recursive):
        for l in self.afc.listdir(dest):
            full_path = os.path.join(dest, l)

            if recursive and IOSFile(self.afc, full_path).is_dir():
                self._rm_dir(full_path, recursive)
            self.afc.remove(full_path)
