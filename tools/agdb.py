#!/usr/bin/env python
# -*- coding: utf-8 -*-

__VERSION__ = '1.0.0'
__author__ = 'rx.wen218@gmail.com'
"""
android cross platform gdb wrapper
"""
import subprocess
import os
import sys
import re
from optparse import OptionParser
from threading import Thread

DEFAULT_PRODUCT_NAME="generic"
DEFAULT_DEBUGGER_NAME = "arm-eabi-gdb"
DEFAULT_FILE_LOCATION = "/system/bin/"
android_src_root = ""
adb_cmds = ["adb"]

def find_debugger(version):
    """
    find android debugger
    return the latest version of all debuggers if version is not specified
    return empty string on failure
    """
    DEFAULT_DEBUGGER_NAME = "arm-eabi-gdb"
    debugger_path = ""
    if sys.platform.startswith("linux"):
        debugger_pattern = ".+linux.+" + version + ".+" + DEFAULT_DEBUGGER_NAME
        p = subprocess.Popen(["find", android_src_root+os.sep+"prebuilt", "-iregex", debugger_pattern], stdout=subprocess.PIPE)
        p.wait()
    output = p.stdout.readlines()
    if len(output) > 0:
        debugger_path = output[len(output)-1].rstrip()
    return debugger_path

def find_pid_of_process(process_name):
    """
    find pid of target process
    return "0" on failure
    """
    number_pattern = "([0-9]+) +"
    process_pattern = "[a-zA-Z_0-9]+ +("+number_pattern+") +.+[./ ]"+process_name
    pid = "0"

    p = subprocess.Popen(adb_cmds + ["shell", "ps"], stdout=subprocess.PIPE)
    p.wait()
    output = p.stdout.readlines()
    # output format of ps command:
    # USER     PID   PPID  VSIZE  RSS     WCHAN    PC         NAME
    # media     33    1     18960  2584  ffffffff afd0b6fc S /system/bin/mediaserver
    # ...
    for l in output:
        m = re.match(process_pattern, l)
        if m:
            pid = m.groups()[0]
    return pid.rstrip()

def find_file_on_device(file_name, path):
    """
    find file_name in specified path
    return "" on failure
    """
    file_path = ""

    p = subprocess.Popen(adb_cmds + ["shell", "ls", path], stdout=subprocess.PIPE)
    p.wait()
    output = p.stdout.readlines()
    for l in output:
        m = re.match("("+file_name+")", l)
        if m:
            file_path = path + "/" + m.groups()[0]
    return file_path

def start_target_process(port, file_name):
    class GdbserverProcessThread(Thread):
        def __init__(self):
            Thread.__init__(self)
        
        def run(self):
            cmd = adb_cmds + ["shell", "gdbserver", ":"+port, file_name]
            pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            #os.system("adb shell gdbserver :" + port + " --attach " + pid + " &")

    th = GdbserverProcessThread()
    th.start()

def kill_process(pid):
    p = subprocess.Popen(adb_cmds + ["shell", "kill", pid])
    p.wait()

def attach_gdbserver(port, pid):
    """
    attach gdbserver to target process
    """
    class GdbserverThread(Thread):
        def __init__(self):
            Thread.__init__(self)
        
        def run(self):
            cmd = adb_cmds + ["shell", "gdbserver", ":"+port, "--attach", pid]
            pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            #os.system("adb shell gdbserver :" + port + " --attach " + pid + " &")

    th = GdbserverThread()
    th.start()

def find_process_symbol(process_name, product_name):
    """
    find symbol file for process
    return empty string on failure
    """
    symbol_root = "%s/out/target/product/%s/symbols/"%(android_src_root, product_name)
    process_symbol = ""
    if sys.platform.startswith("linux"):
        process_symbol_pattern = ".+" + process_name 
        p = subprocess.Popen(["find", symbol_root, "-iregex", process_symbol_pattern], stdout=subprocess.PIPE)
        p.wait()
    output = p.stdout.readlines()
    if(len(output) > 0):
        process_symbol = output[0].rstrip()
    return process_symbol 

def start_gdb_client(debugger, process, product_name, debugger_wrapper_type = "gdb"):
    lib_symbol_prefix = "%s/out/target/product/%s/symbols/"%(android_src_root, product_name) 
    lib_symbol_root = "%s/out/target/product/%s/symbols/system/lib"%(android_src_root, product_name)
    cmdl = '%s %s -ex "set solib-absolute-prefix %s" -ex "set solib-search-path %s"'%(debugger, process, 
            lib_symbol_prefix, lib_symbol_root)
    # run gdb under cgdb 
    if debugger_wrapper_type == "cgdb":
        cmdl = "cgdb -d " + cmdl
    os.system(cmdl)

if __name__ == "__main__":
    debugger_wrappers = ["gdb", "cgdb", "ddd"]
    KEY_ANDROID_SRC_ROOT = "ANDROID_SRC_ROOT"
    default_android_src_root = ""
    if os.environ.has_key(KEY_ANDROID_SRC_ROOT):
        default_android_src_root = os.environ[KEY_ANDROID_SRC_ROOT]

    # parse command line options
    opt_parser = OptionParser(version = "%prog " + __VERSION__, 
                description = "wrapper on android gdb",
                usage = "%prog [options] process_name")
    opt_parser.add_option("", "--android-src-root", dest="android_src_root", default=default_android_src_root, 
            help="root of android source tree, can be set via "+KEY_ANDROID_SRC_ROOT+" environment variable")
    opt_parser.add_option("-d", "--debugger-wrapper", dest="debugger_wrapper", default=debugger_wrappers[0], 
            help="wrappers on gdb, e.g., cgdb, ddd")
    opt_parser.add_option("-k", "--kill", action="store_true", default=False, 
            help="kill process on target [default: %default]")
    opt_parser.add_option("", "--debugger-version", dest="debugger_version", default="", 
            help="specify a debugger version, e.g., 4.4.0, 4.2, 4. Will use the latest version if not specified")
    opt_parser.add_option("", "--product-name", dest="product_name", default=DEFAULT_PRODUCT_NAME, 
            help="product name, [default: %default]")
    opt_parser.add_option("-l", "--location", dest="file_location", default=DEFAULT_FILE_LOCATION, 
            help="the directory to search for process file on target, [default: %default]")
    opt_parser.add_option("-p", "--port", dest="gdb_port", default="7890", 
            help="port used for gdbserver, [default: %default]")
    opt_parser.add_option("-s", "", dest="serial_number", default="", 
            help="direct commands to device with given serial number.")
    (cmdline_options, args) = opt_parser.parse_args()
    if len(args) < 1:
        print "must specify process name"
        sys.exit(-1)
    process_name = args[0]
    if cmdline_options.android_src_root == None or cmdline_options.android_src_root == "":
        print "android-src-root must be set"
        sys.exit(-1)
    else:
        android_src_root = cmdline_options.android_src_root

    if cmdline_options.serial_number != "":
        adb_cmds += ["-s", cmdline_options.serial_number]

    if cmdline_options.kill:
        pid = find_pid_of_process(process_name)
        if pid != "0":
            kill_process(pid)
            print "killed "+process_name+ ", pid is: " + pid 
        else:
            print process_name + " not found  on target."
        sys.exit(0)

    debugger = find_debugger(cmdline_options.debugger_version)
    if debugger == "":
        print "fail to find " + DEFAULT_DEBUGGER_NAME + ". Did you build android source?"
        sys.exit(-1)
    print "found debugger: " + debugger

    process_symbol = find_process_symbol(process_name, cmdline_options.product_name)
    if process_symbol == "":
        print "fail to find symbol for " + process_name + ". Did you build android source?"
        sys.exit(-1)
    print "found symbol: " + process_symbol 

    pid = find_pid_of_process(process_name)
    if pid == "0":
        print process_name + " process not found on target. try to start it"
        file_name = find_file_on_device(process_name, path=cmdline_options.file_location)
        if file_name == "":
            print process_name + " file not found on target. exit"
            sys.exit(-1)
        else:
            print "found "+process_name+ ", file path is: " + file_name 
            start_target_process(cmdline_options.gdb_port, file_name)
            print "start %s under gdbserver, listen on port %s"%(file_name, cmdline_options.gdb_port)
    else:
        print "found "+process_name+ ", pid is: " + pid 
        attach_gdbserver(cmdline_options.gdb_port, pid)
        print "attach gdbserver to %s, listen on port %s"%(pid, cmdline_options.gdb_port)

    start_gdb_client(debugger, process_symbol, cmdline_options.product_name, 
            debugger_wrapper_type=cmdline_options.debugger_wrapper)