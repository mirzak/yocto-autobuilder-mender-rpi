'''
Created on Jan 7, 2016

__author__ = "Tracy Graydon"
__copyright__ = "Copyright 2016, Intel Corp."
__credits__ = ["Tracy Graydon"]
__license__ = "GPL"
__version__ = "2.0"
__maintainer__ = "Tracy Graydon"
__email__ = "tracy.graydon@intel.com"
'''

import os
import optparse
import sys
import hashlib
import glob
import os.path
import shutil
from shutil import rmtree, copyfile
from subprocess import call

def sanity_check(source, target):
    if not os.path.exists(source):
       print
       print "SOURCE dir %s does NOT EXIST." %source
       print
       sys.exit()
    if not os.listdir(source):
       print
       print "SOURCE dir %s is EMPTY" %source
       print
    if os.path.exists(target):
       print
       print "I can't let you do it, Jim. The TARGET directory %s exists." %target
       print
       sys.exit()
    return

def sync_it(source, target, exclude_list):
    print "Syncing %s to %s" %(source, target)
    sanity_check(source, target)
    source = source + "/"
    if exclude_list:
        exclusions = ['--exclude=%s' % x.strip() for x in exclude_list]
        print "Exclusions: %s" %exclusions
        print
        exclude = "--exclude=" + os.path.join(RELEASE_DIR, exclude_list[0])
        length = len(exclude_list)
        for i in range(1, length):
            exclude = exclude + " " + "--exclude=" + os.path.join(RELEASE_DIR, exclude_list[i])
        print "Exclude: %s" %exclude
        command = "rsync -avrl " + exclude + source + " " + target
        os.system("rsync -avrl --exclude=deb --exclude=rpm --exclude=ptest --exclude=adt-installer-QA '%s' '%s'" %(source, target))
    else:
        os.system("rsync -avrl '%s' '%s'" %(source, target))
    print
    return

def purge_unloved():
    print
    print "Purging unwanted directories..."
    for target in UNLOVED:
        target = target.rstrip()
        print "Deleting: %s/%s" %(RELEASE_DIR, target)
        os.system('rm -rf %s/%s' %(RELEASE_DIR, target))
    return

def get_list(dirname):
    dirlist = os.listdir(dirname)
    dirlist.sort()
    return dirlist

def split_thing(thing, marker):
    filebits = thing.split(marker)
    return filebits

def rejoin_thing(thing, marker):
    filebits = marker.join(thing)
    return filebits

def fix_tarballs():
    print
    print "Repackaging poky and eclipse tarballs...."
    os.chdir(RELEASE_DIR)
    os.mkdir(TARBALL_DIR)
    os.system("mv %s/*.tar.bz2 %s" %(RELEASE_DIR, TARBALL_DIR))
    os.system("rm *.md5sum")
    os.chdir(TARBALL_DIR)
    dirlist = get_list(TARBALL_DIR)
    for blob in dirlist:
        print "Original Tarball: %s" %blob
        chunks = split_thing(blob, ".")
        filename = chunks[0]
        basename = split_thing(filename, "-")
        index = len(basename)-1
        basename[index] = "-".join([BRANCH, POKY_VER])
        new_name = rejoin_thing(basename, "-")
        chunks[0] = new_name
        new_blob = rejoin_thing(chunks, ".")
        print "New Tarball: %s" %new_blob
        os.system("tar jxf %s" %blob)
        os.system("mv %s %s" %(filename, new_name))
        os.system("rm -rf %s/.git*" %new_name)
        os.remove(blob)
        os.system("tar jcf %s %s" %(new_blob, new_name))
        rmtree(new_name)
        os.symlink(new_blob, blob)
        os.system("md5sum %s > %s.md5sum" %(new_blob, new_blob))
        print
    os.system("mv * %s" %RELEASE_DIR)
    os.chdir(RELEASE_DIR)
    os.rmdir(TARBALL_DIR)
    print
    return

def get_md5sum(path, blocksize = 4096):
    f = open(path, 'rb')
    md5sum = hashlib.md5()
    buffer = f.read(blocksize)
    while len(buffer) > 0:
        md5sum.update(buffer)
        buffer = f.read(blocksize)
    f.close()
    return md5sum.hexdigest()

def convert_symlinks(dirname):
    thing = os.path.split(dirname)[1]
    if thing == "qemu":
        dirlist = get_list(dirname)
        for dir in dirlist:
            qemu_dir = os.path.join(MACHINES, dirname, dir)
            print "Converting symlinks in %s" %qemu_dir
            convert_symlinks(qemu_dir)
    else:
        print "Converting symlinks in %s" %dirname
        link_list = []
        for root, dirs, files in os.walk(dirname, topdown=True):
            for name in files:
                filename = (os.path.join(root, name))
                if os.path.islink(filename):
                    src_file = os.path.realpath(filename)
                    link_list.append([filename, src_file])
        for line in link_list:
            os.remove(line[0])
            try:
               copyfile(line[1], line[0])
            except IOError:
                print "Error: %s is missing or isn\'t a real file" %line[1]
            else:
                print line[0]
        for line in link_list:
            if os.path.exists(line[1]):
               os.remove(line[1])
    print
    return

def find_dupes(dirname, platform):
    print "\nLooking for duplicate files in %s" %dirname
    file_list = []
    md5sum_list = []
    for root, dirs, files in os.walk(dirname, topdown=True):
        for name in files:
            filename = (os.path.join(root, name))
            md5sum = get_md5sum(filename)
            file_list.append((filename, md5sum))
            md5sum_list.append(md5sum)
    s=set(md5sum_list)
    d=[]
    for x in file_list:
        if x[1] in s:
            s.remove(x[1])
        else:
            d.append(x[1])
    for dupe in d:
        for tup in file_list:
            if tup[1] == dupe:
                dupe_name = split_thing(tup[0],"/")
                filename = dupe_name[-1]
                if filename.find(platform) == -1:
                    print "Deleting %s" %tup[0]
                    os.remove(tup[0])
    return

def make_bsps(bsp_list, bsp_dir):
    print "\nCreating bsps.....\n"
    if not os.path.exists(bsp_dir):
        os.mkdir(bsp_dir)
    else:
        print "BSP tarball dir exists! Skipping BSP creation."
        return
    poky_blob = os.path.join(RELEASE_DIR, POKY_TARBALL)
    blob_dir = split_thing(POKY_TARBALL, ".")
    blob_dir = rejoin_thing(blob_dir[:-2], ".")
    os.chdir(bsp_dir)
    for dirname in bsp_list:
        platform_dir = os.path.join(MACHINES, dirname)
        if os.path.exists(platform_dir):
            if not os.path.exists(dirname):
                print "Creating %s bsp dir" %dirname
                os.mkdir(dirname)
            target = os.path.join(dirname, POKY_TARBALL)
            oldblob = POKY_TARBALL
            chunks = split_thing(oldblob, "-")
            chunks[0] = dirname
            new_blob = rejoin_thing(chunks, "-")
            print "BSP tarball: %s" %new_blob
            new_dir = split_thing(blob_dir, "-")
            new_dir[0] = dirname
            new_dir = rejoin_thing(new_dir, "-")
            bin_dir = os.path.join(new_dir, "binary")
            copyfile(poky_blob, target)
            os.chdir(dirname)
            print "Unpacking poky tarball."
            os.system("tar jxf %s" %POKY_TARBALL)
            shutil.move(blob_dir, new_dir)
            os.remove(POKY_TARBALL)
            if not os.path.exists(bin_dir):
                os.mkdir(bin_dir)
            print "Getting binary files"
            os.system("rsync -arl %s/%s/ %s" %(MACHINES, dirname, bin_dir))
            bsp_bin = os.path.join(bsp_dir, dirname, bin_dir)
            nuke_cruft(bin_dir, BSP_JUNK)
            bsp_path = os.path.join(bsp_dir, dirname, bin_dir)
            find_dupes(bsp_path, dirname)
            print "Creating BSP tarball"
            os.system("tar jcf %s %s" %(new_blob, new_dir))
            rmtree(new_dir)
            print "Generating the md5sum."
            os.system("md5sum %s > %s.md5sum" %(new_blob, new_blob))
            print "Copying %s BSP to platform dir" %dirname
            os.system("mv * %s" %platform_dir)
            os.chdir(bsp_dir)
        print
    os.chdir(RELEASE_DIR)
    rmtree(bsp_dir)
    return

def nuke_cruft(dirname, ext_list):
    thing = os.path.split(dirname)[1]
    if thing == "qemu":
        dirlist = get_list(dirname)
        for dir in dirlist:
            qemu_dir = os.path.join(MACHINES, dirname, dir)
            nuke_cruft(qemu_dir, CRUFT_LIST)
    else:
        for ext in ext_list:
            print "Deleting %s files" %ext
            os.system("rm -f %s/%s" %(dirname, ext))
    print
    return

def pub_eclipse(EDIR, PDIR):
    print "\nPublishing Eclipse plugins."
    sanity_check(EDIR, PDIR)
    os.system("mkdir -p %s" %PDIR)
    for root, dirs, files in os.walk(EDIR, topdown=True):
        for name in dirs:
            target_dir = os.path.join(PDIR, name)
            os.system("mkdir -p %s" %target_dir)
            source_dir = os.path.join(EDIR, name)
            filelist = get_list(source_dir)
            found = filter(lambda x: 'archive' in x, filelist).pop()
            source = os.path.join(EDIR, name, found)
            target = os.path.join(target_dir, found)
            print "Source: %s" %source
            print "Target: %s" %target
            copyfile(source, target)
            os.chdir(target_dir)
            os.system("unzip -o '%s'" %found)
            os.system("rm -vf %s" %found)
            print
    return

def gen_md5sum(dirname):
    print
    print "Generating md5sums for files in %s...." %dirname
    for root, dirs, files in os.walk(dirname, topdown=True):
        for name in files:
            filename = (os.path.join(root, name))
            md5sum = get_md5sum(filename)
            md5_file = ".".join([filename, 'md5sum'])
            md5str = md5sum + " " + name
            print md5str
            f = open(md5_file, 'w')
            f.write(md5str)
            f.close()
    return

def gen_rel_md5(dirname, md5_file):
    os.chdir(RELEASE_DIR)
    print "Generating master md5sum file %s" %md5_file
    f = open(md5_file, 'w')
    for root, dirs, files in os.walk(dirname, topdown=True):
        for name in files:
            filename = (os.path.join(root, name))
            ext = split_thing(name, ".")[-1]
            if not (ext == "md5sum" or ext == "txt"):
                relpath = split_thing(filename, RELEASE_DIR)
                relpath.pop(0)
                relpath = relpath[0]
                relpath = split_thing(relpath, "/")
                relpath.pop(0)
                relpath = rejoin_thing(relpath, "/")
                relpath = "./" + relpath
                print relpath
                md5sum = get_md5sum(filename)
                print md5sum
                md5str = md5sum + " " + relpath
                print md5str
                f.write(md5str + '\n')
    f.close()
    return

def publish_adt(rel_id, rel_type, opts):
    if opts:
        ADT_DIR = os.path.join(ADT_BASE, opts)
    else:
        if rel_type == "milestone":
            chunks = split_thing(rel_id, "_")
            id_thing = float(chunks[0])
            id_thing = id_thing - 0.1
            rel_id = str(id_thing) + "+" + "snapshot"
        ADT_DIR = os.path.join(ADT_BASE, rel_id)
    print "ADT_DIR: %s" %ADT_DIR
    if os.path.exists(ADT_DIR):
        print "ADT_DIR %s EXISTS! Refusing to clobber!" %ADT_DIR
        sys.exit()
    else:
        ADT_ROOTFS = os.path.join(ADT_DIR, "rootfs")
        ADT_IPK = os.path.join(ADT_DIR, "adt-ipk")
        QEMU_DIR = os.path.join(MACHINES, "qemu")
        IPK_DIR = os.path.join(RELEASE_DIR, "ipk")
        os.mkdir(ADT_DIR)
        os.mkdir(ADT_ROOTFS)
        dirlist = get_list(QEMU_DIR)

        for dirname in dirlist:
            QEMU_SRC = os.path.join(QEMU_DIR, dirname)
            QEMU_TARGET = os.path.join(ADT_ROOTFS, dirname)
            print "QEMU_SRC: %s" %QEMU_SRC
            sync_it(QEMU_SRC, QEMU_TARGET, "")
        sync_it(IPK_DIR, ADT_IPK, "")
    return

if __name__ == '__main__':
    
    os.system("clear")
    print
   
    VHOSTS = "/srv/www/vhosts"
    AB_BASE = os.path.join(VHOSTS, "autobuilder.yoctoproject.org/pub/releases")
    DL_DIR = os.path.join(VHOSTS, "downloads.yoctoproject.org/releases")
    DL_BASE = os.path.join(DL_DIR, "/releases/yocto")
    ADT_BASE = os.path.join(VHOSTS, "adtrepo.yoctoproject.org")

    # List of the directories we delete from all releases
    UNLOVED = ['rpm', 'deb', 'ptest', 'adt-installer-QA']
    # List of the files in machines directories that we delete from all releases
    CRUFT_LIST = ['*.md5sum', '*.tar.gz', '*.iso']
    # List of the platforms for which we want to generate BSP tarballs. Major and point releases.
    BSP_LIST = ['beaglebone', 'edgerouter', 'genericx86', 'genericx86-64']
    # List of files we do not want to include in the BSP tarballs.
    BSP_JUNK = ['*.manifest', '*.tar.bz2', '*.tgz', '*.iso', '*.md5sum', '*.tar.gz', '*-dev-*', '*-sdk-*']

    parser = optparse.OptionParser()
    parser.add_option("-i", "--build-id",
                      type="string", dest="build",
                      help="Required. Release candidate name including rc#. i.e. yocto-2.0.rc1, yocto-2.1_M1.rc3, etc.")
    parser.add_option("-b", "--branch",
                      type="string", dest="branch",
                      help="Required for Major and Point releases. i.e. daisy, fido, jethro, etc.")
    parser.add_option("-p", "--poky-ver",
                      type="string", dest="poky",
                      help="Required for Major and Point releases. i.e. 14.0.0")
    parser.add_option("-a", action="store_true", dest="pub_adt",
                      help="Publish an ADT repo for the release. Default is NOT to publish.")
    parser.add_option("-d", "--adt-dir",
                      type="string", dest="adt_dir",
                      help="Use when you need to publish the ADT repo to a custom location. i.e. python adtcopy -b yocto-2.0_M1.rc1 -a 1.8+snaphot")

    (options, args) = parser.parse_args()
 
    REL_TYPE = ""
    MILESTONE = ""
    if options.poky:
        POKY_VER = options.poky
    else:
        POKY_VER = ""
    if options.branch:
        BRANCH = options.branch
    else:
        BRANCH = ""

    if options.build:
        # Figure out the release name, type of release, and generate some vars, do some basic validation
        options.build = options.build.lower()
        RC = split_thing(options.build, ".")[-1]
        chunks = split_thing(options.build, ".") # i.e. split yocto-2.1_m1.rc1
        chunks.pop()
        chunks[1] = chunks[1].upper()
        RELEASE = rejoin_thing(chunks, ".")  # i.e. yocto-2.1_m1
        REL_ID = split_thing(RELEASE, "-")[-1].upper()
        RC_DIR = rejoin_thing([RELEASE, RC], ".")
        RC_SOURCE = os.path.join(AB_BASE, RC_DIR)
        if not os.path.exists(RC_SOURCE):
            print "%s does not appear to be a valid RC dir. Check your args." %RC_SOURCE
            sys.exit()
        relstring = split_thing(REL_ID, "_")
        if len(relstring) == 1:
            thing = split_thing(relstring[0], ".")
            if len(thing) == 3:
                REL_TYPE = "point"
            elif len(thing) == 2:
                REL_TYPE = "major"
            if options.poky and options.branch:
                POKY_VER = options.poky
                BRANCH = options.branch
            else:
                print "You can't have a major or point release without a branch and a poky version. Check your args."
                print "Please use -h or --help for options."
                sys.exit()
        else:
            MILESTONE = relstring.pop()
            REL_TYPE = "milestone"
    else:
        print "Build ID is a required argument."
        print "Please use -h or --help for options."
        sys.exit()
   
    if not (RELEASE and RC and REL_ID and REL_TYPE):
        print "Can't determine the release type. Check your args."
        print "You gave me: %s" %options.build
        sys.exit()
    
    print "RC_DIR: %s" %RC_DIR
    print "RELEASE: %s" %RELEASE
    print "RC: %s" %RC
    print "REL_ID: %s" %REL_ID
    print "REL_TYPE: %s" %REL_TYPE
    if MILESTONE:
        print "MILESTONE: %s" %MILESTONE
    print

    PLUGIN_DIR = os.path.join(DL_DIR, "eclipse-plugin", REL_ID)
    RELEASE_DIR = os.path.join(AB_BASE, RELEASE)
    MACHINES = os.path.join(RELEASE_DIR, "machines")
    BSP_DIR = os.path.join(RELEASE_DIR, 'bsptarballs')
    TARBALL_DIR = os.path.join(RELEASE_DIR, "tarballs")
    POKY_TARBALL = "poky-" + BRANCH + "-" + POKY_VER + ".tar.bz2"
    ECLIPSE_DIR = os.path.join(RELEASE_DIR, "eclipse-plugin")
    BUILD_APP_DIR = os.path.join(RELEASE_DIR, "build-appliance")
    REL_MD5_FILE = RELEASE + ".md5sum"

    # For all releases:
    # 1) Rsync the rc candidate to a staging dir where all work happens
    sync_it(RC_SOURCE, RELEASE_DIR, UNLOVED)
    
    # 2) Convert the symlinks in build-appliance dir.
    print "Converting the build-appliance symlink."
    convert_symlinks(BUILD_APP_DIR)

    # 3) In machines dir, convert the symlinks, delete the cruft
    print "Cleaning up the machines dirs, converting symlinks."
    dirlist = get_list(MACHINES)
    for dirname in dirlist:
        dirname = os.path.join(MACHINES, dirname)
        convert_symlinks(dirname)
        nuke_cruft(dirname, CRUFT_LIST)
    print "Generating fresh md5sums."
    gen_md5sum(MACHINES)
    
    # For major and point releases
    if REL_TYPE == "major" or REL_TYPE == "point":
        # 4) Fix up the eclipse and poky tarballs
        print "Cleaning up the eclipse, poky and other tarballs."
        fix_tarballs()

        # 5) Publish the eclipse stuff
        print "Publishing the eclipse plugins."
        pub_eclipse(ECLIPSE_DIR, PLUGIN_DIR)

        # 6) Make the bsps
        print "Generating the BSP tarballs."
        make_bsps(BSP_LIST, BSP_DIR)

        # 7) Generate the master md5sum file for the release (for all releases)
        print "Generating the master md5sum table."
        gen_rel_md5(RELEASE_DIR, REL_MD5_FILE)
    
    # 8) Publish the ADT repo. The default is NOT to publish the ADT. The ADT
    # is deprecated as of 2.1_M1. However, we need to retain backward
    # compatability for point releases, etc. We do this step after all the other
    #  stuff because we want the symlinks to have been converted, extraneous
    # files deleted, and md5sums generated.
    #
    if options.pub_adt:
        if options.adt_dir:
            print "Publishing the ADT repo using custom dir %s" %options.adt_dir
            publish_adt(REL_ID, REL_TYPE, options.adt_dir)
        else:
            print "Publishing ADT repo."
            publish_adt(REL_ID, REL_TYPE, "")
