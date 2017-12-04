#!/usr/bin/env python

import argparse
import logging
import time
import serial
import hexdump
import colorama

DESCSTRING = """Interact with Velocio PLC
Control Instructions:
    play 			start the routine at current position
    pause			pause the routine at current position
    reset			reset the routine to the beginning
    set_output_1_off	set output 1 to off
    set_output_2_off	set output 2 to off
    set_output_3_off	set output 3 to off
    set_output_4_off	set output 4 to off
    set_output_5_off	set output 5 to off
    set_output_6_off	set output 6 to off
    set_output_1_on		set output 1 to on
    set_output_2_on		set output 2 to on
    set_output_3_on		set output 3 to on
    set_output_4_on		set output 4 to on
    set_output_5_on		set output 5 to on
    set_output_6_on		set output 6 to on

Read Instructions:
    read_input_bits		query the input bits and print the response
    read_output_bits	query the output bits and print the response
    read_tags           get the friendly names of tags on the device

Debug Instructions:
    enter_debug		put the device into debug mode for testing
    exit_debug		exit the device debug mode for normal operation
    step_into		standard procedure
    step_out		standard procedure
    step_over		standard procedure
"""


# read instructions
READ_INPUT_BITS = [
    "\x56\xff\xff\x00\x08\x0a\x00\x01",
    "\x56\xff\xff\x00\x08\x0a\x00\x02",
    "\x56\xff\xff\x00\x08\x0a\x00\x03",
    "\x56\xff\xff\x00\x08\x0a\x00\x04",
    "\x56\xff\xff\x00\x08\x0a\x00\x05",
    "\x56\xff\xff\x00\x08\x0a\x00\x06"
]

READ_OUTPUT_BITS = [
    "\x56\xff\xff\x00\x08\x0a\x00\x07",
    "\x56\xff\xff\x00\x08\x0a\x00\x08",
    "\x56\xff\xff\x00\x08\x0a\x00\x09",
    "\x56\xff\xff\x00\x08\x0a\x00\x0a",
    "\x56\xff\xff\x00\x08\x0a\x00\x0b",
    "\x56\xff\xff\x00\x08\x0a\x00\x0c"
]

COMMAND_IMPLEMENTATIONS = {
    "play":             ["\x56\xff\xff\x00\x07\xf1\x01"],
    "pause":            ["\x56\xff\xff\x00\x07\xf1\x02"],
    "reset":            ["\x56\xff\xff\x00\x07\xf1\x06"],
    "step_into":        ["\x56\xff\xff\x00\x07\xf1\x03"],
    "step_out":         ["\x56\xff\xff\x00\x07\xf1\x04"],
    "step_over":        ["\x56\xff\xff\x00\x07\xf1\x05"],
    "enter_debug":      ["\x56\xff\xff\x00\x07\xf0\x02"],
    "exit_debug":       ["\x56\xff\xff\x00\x07\xf0\x01"],
    "set_output_1_off": ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x01\x00\x00\x00"],
    "set_output_2_off": ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x02\x00\x00\x00"],
    "set_output_3_off": ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x04\x00\x00\x00"],
    "set_output_4_off": ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x08\x00\x00\x00"],
    "set_output_5_off": ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x10\x00\x00\x00"],
    "set_output_6_off": ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x20\x00\x00\x00"],
    "set_output_1_on":  ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x01\x00\x00\x01"],
    "set_output_2_on":  ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x02\x00\x00\x01"],
    "set_output_3_on":  ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x04\x00\x00\x01"],
    "set_output_4_on":  ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x08\x00\x00\x01"],
    "set_output_5_on":  ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x10\x00\x00\x01"],
    "set_output_6_on":  ["\x56\xff\xff\x00\x15\x11\x01\x00\x01\x00\x00\x09\x01\x00\x00\x01\x00\x20\x00\x00\x01"],
    "read_input_bits":  READ_INPUT_BITS,
    "read_output_bits": READ_OUTPUT_BITS,
    "read_tags":        ["\x56\xff\xff\x00\x06\xac"]
}

TAG_COUNT_HEADER    = "56FFFF000AAC06".decode('hex')
TAG_READNAME_HEADER = "56ffff00080a00".decode('hex')


def cb_default(ser, cname, respdata):
    logging.debug("Response for command %s" % cname)
    for l in hexdump.dumpgen(respdata):
        logging.debug(colorama.Fore.GREEN + l + colorama.Style.RESET_ALL)


def cb_read_tags(ser, cname, respdata):
    if str(respdata).startswith(TAG_COUNT_HEADER):
        numtags = ord(respdata[-1])
        logging.info("Reading %d tag names..." % numtags)
        for i in xrange(1, numtags+1):
            r = write_ser_get_response(ser, TAG_READNAME_HEADER + chr(i))
            tname = r[9:].split(" ")[0]
            logging.info("Read tag %d name: \t%s" % (i, colorama.Fore.CYAN + tname + colorama.Style.RESET_ALL))
    else:
        logging.error("Unexpected response for tag count: ")
        for l in hexdump.dumpgen(respdata):
            logging.error(colorama.Fore.RED + l + colorama.Style.RESET_ALL)


COMMAND_CALLBACKS = {
    "read_tags": cb_read_tags
}


def connect_serial():
    ser = serial.Serial(
        port='/dev/ttyACM0',
        baudrate=9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS
    )
    ser.isOpen()
    return ser


def write_ser_get_response(ser, insn):
    ser.write(insn)
    time.sleep(0.1)
    response = ""
    while ser.inWaiting() > 0:
        response += ser.read()
    time.sleep(0.1)
    return response


def send_command_read_response(ser, cname):
    # clear out any leftover data
    if ser.inWaiting() > 0:
        ser.flushInput()

    logging.info("Sending command: %s" % cname)

    for insn in COMMAND_IMPLEMENTATIONS[cname]:
        response = write_ser_get_response(ser, insn)

        # Handle any response data
        if cname in COMMAND_CALLBACKS:
            COMMAND_CALLBACKS[cname](ser, cname, response)
        else:
            cb_default(ser, cname, response)


def process_command(incommand):
    c = incommand[0]
    if c not in COMMAND_IMPLEMENTATIONS:
        logging.error("Unknown command - please check usage")
        return

    # Got a real command, so connect up
    ser = connect_serial()

    # Execute it and read output if needed
    send_command_read_response(ser, c)

    # Clean up
    ser.close()


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description=DESCSTRING, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("command", metavar="command", type=str, nargs=1, help="Command to execute (-h for a list)")
    parser.add_argument("--loglevel", dest="loglevel", type=str, default="info",
                        help="Logging level (info, debug, etc)")
    args = parser.parse_args()

    # Enable logging
    numeric_level = getattr(logging, args.loglevel.upper(), logging.INFO)
    logging.basicConfig(format='%(levelname)s:%(message)s', level=numeric_level)

    logging.debug("Starting up")

    process_command(args.command)

    logging.info("Done")


if __name__ == "__main__":
    main()
