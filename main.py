#!/usr/bin/python3
import argparse
import os
import re
import queue
import threading
import sys
import lxml.etree as et
import xml.etree.ElementTree as xet

from queue import Queue
from termcolor import colored, cprint

# Connector to use for representing flattened structure of chained nodes in
# the map
NODE_CONNECTOR = " --> "

# Substitute Linebreak to use instead of actual line break when printing flattened structure
LINEBREAK = " \\n "

# Default freeplane map extensions
FREEPLANE_MAPS_EXTENSIONS = ".mm"

# Color to use for file name where matches were found 
FILEPATH_COLOR = "green"

# Color to use for matched text
MATCH_COLOR = "red"

# Initial Block period (in seconds)
INIT_BLOCK_PERIOD = 1

# Description for this Script 
DESCRIPTION = """
Script to parse and search Freeplane MindMap XML files
"""

# New Line replacement character
NEW_LINE_REPLACEMENT = "\\n"

# Global flag to indicate when user interrupts e.g. via CTRL-C
user_interrupt_flag = threading.Event()

# Print queue to be used for printing results
print_queue = None

# Search tasks queue for files to search
search_tasks_queue = None

# Verbose flag to print messages
verbose_flag = False

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    """Class for custom formatting of Argparse
    """
    pass

def error(msg):
    """Print error message

    Args:
        msg (msg): Error message
    """
    text = colored("[-] " + msg, "red")
    print(text)

def debug(msg):
    """Print debug message

    Args:
        msg (msg): Error message
    """
    global verbose_flag

    if verbose_flag:
        print("[*] " + msg)

def open_freeplane_map(map_file, validate_only=False):
    """Open the Freeplane XML map and parse the Freeplane map recursively

    Args:
        map_file (str): Freeplane XML Mindmap file to parse
        validate_only (bool, optional): Whether to validate Freeplane Map. Defaults, False.

    Returns:
        list: Structure of the Mindmap one-per-line
    """
    map_structure = []
    if not os.path.isfile(map_file):
        error(f"File: {map_file} not found")
    else:
        try:
            if validate_only:
                # Validating the mindmap only
                tree = xet.parse(map_file)
            else:

                # Parse the freeplane mindmap with lxml for limited errors
                # and parsing
                parser = et.XMLParser(recover=True)
                tree = et.parse(map_file, parser=parser)
                
                # Parse the root ('map' tag)
                root = tree.getroot()

                # Parse each node
                for c in root:
                    if c.tag == 'node': 
                        flatten_freeplane_node(map_structure, '', c)
        except Exception as e:
            error(f"Exception parsing freeplane map: {map_file}. Error: {e.__class__}, {e}")

    return map_structure

def flatten_freeplane_node(map_structure, prev_text, node):
    """Parse Freeplane child nodes recursively

    Args:
        map_structure (list): Map structure to parse
        prev_text (str): Previous text for this freeplane chain of nodes
        node (xml.etree.ElementTree): XML element to recursively parse and flatten
    """
    num_children_processed = 0
    current_node_text = node.attrib.get('TEXT', '')
    prev_text += NODE_CONNECTOR + current_node_text
    for c in node:
        if c.tag == 'node':
            flatten_freeplane_node(map_structure, prev_text, c)
            num_children_processed += 1

    # If we reach the end of the chain, that is one single flow
    if num_children_processed == 0:
        map_structure.append(prev_text)

def search_freeplane_map(filepath, map_structure, keywords, delimiter, replace_newlines, 
    case_sensitive=False):
    """Search the Freeplane map

    Args:
        filepath (str): File path to search maps used for printing  
        map_structure (dict): Structure of map
        keywords (str): Regex string to search for in the map
        delimiter (str): Delimiter to use form multiple keywords
        replace_newlines (bool): Replace new lines
        case_sensitive (bool, optional): Whether the search should be case-sensitive or not. Defaults, False

    Returns:
        list: List of string matches found that have the keywords that were found (that are color formatted)
    """
    lines_found = []

    # Get the list of keywords to search for
    keywords_arr = keywords.split(delimiter)

    debug(f"Searching freeplane map: {filepath} for keywords: {keywords}...")
    for l in map_structure:

        # Assume keywords match has been found
        kw_match_found = True

        # Search for keywords and ensure that they are found
        line_to_search = l
        for kw in keywords_arr:
    
            if case_sensitive:
                ms = re.search(kw, line_to_search)
            else:
                ms = re.search(kw, line_to_search, re.I)
            if ms:

                # Simply, color the keywords discovered in the line
                if case_sensitive:
                    line_to_search = re.sub(kw, lambda m: colored(m.group(), MATCH_COLOR) , line_to_search)
                else:
                    line_to_search = re.sub(kw, lambda m: colored(m.group(), MATCH_COLOR) , line_to_search, flags=re.I)
                
                # Replace the new lines with characters to replace new lines
                if replace_newlines:
                    line_to_search = line_to_search.replace("\n", LINEBREAK)
                    line_to_search = line_to_search.replace("\r", LINEBREAK)
            else:
                # Match wasn't found in line, stop searching
                kw_match_found = False
                break

        # If keywords found, then append
        if kw_match_found:
            lines_found.append(line_to_search)

    return lines_found

def print_matches(block_period=INIT_BLOCK_PERIOD):
    """Pretty format and print the matches found to the user

    Args:
        block_period(int): Block period to wait for matches to print
    """
    global print_queue

    continue_thread = True
    while continue_thread:
        rv = None
        try:
            rv = print_queue.get(block=True, timeout=block_period)
        except queue.Empty:
            pass

        if rv:
            map_file, matches = rv['file'], rv['matches']

            if matches:
                print(colored(map_file, FILEPATH_COLOR))
                for l in matches:
                    print(l)
                print()
        else:
            continue_thread = False


def init_print_queue():
    """
    Returns a queue which contains the matches that were found in each queue

    Returns:
        Queue: A queue that consists of matches to print for each file (a dict which consists of a 'file' and 'matches')
    """
    global print_queue

    if not print_queue:
        print_queue = Queue()
    return print_queue

def put_on_print_queue(filepath, matches):
    """Put file path and matches found on the print queue for printing

    Args:
        filepath (str): File path for which matches were found
        matches (list): List of matches for the file
    """
    global print_queue

    debug(f"Putting matches: {len(matches)} found for filepath: {filepath}...")
    print_queue.put(
        {'file': filepath,
        'matches': matches}
    )

def init_search_tasks_queue():
    """
    Returns:
        Queue: A queue that consists of collection of files to search
    """
    global search_tasks_queue

    if not search_tasks_queue:
        search_tasks_queue = Queue()
    return search_tasks_queue

def put_search_tasks(filepath):
    """Put a search task which specifies the filepath to search

    Args:
        filepath (str): Filepath to search
    """
    global search_tasks_queue
    search_tasks_queue.put(filepath)

def open_map_and_search(keywords, delimiter, case_sensitive, replace_newlines, 
    validate_only=False, block_period=INIT_BLOCK_PERIOD):
    """Open a single map from the queue and search

    Args:
        keywords (str): Keywords to search for in the map file
        delimiter (str): Delimiter to use for multiple keywords
        case_sensitive (bool): Case sensitive
        replace_newlines (str): Newlines for replacement
        validate_only (bool): Whether to only validate the freeplane map instead of continuing to 
            parse to show any errors. Defaults, False. 
    """
    global user_interrupt_flag, search_tasks_queue

    continue_thread = True
    while continue_thread:

        # Get the file path to search 
        filepath = None
        try:
            filepath = search_tasks_queue.get(block=True, timeout=block_period)
        except queue.Empty:
            pass

        if filepath:

            # Open the freeplane map
            did_user_interrupt = user_interrupt_flag.is_set()
            if not did_user_interrupt:
                map_structure = open_freeplane_map(filepath, validate_only)
            else:
                continue_thread = False

            # if validating freeplane mindmaps only, then we don't search for keywords...
            if not validate_only:
                # Search the freeplane map for the keywords
                did_user_interrupt = user_interrupt_flag.is_set()
                if not did_user_interrupt:
                    lines_found = search_freeplane_map(filepath, map_structure, keywords, delimiter, 
                        replace_newlines, case_sensitive)
                else:
                    continue_thread = False

                # Put the lines found from print queue for printing to terminal
                did_user_interrupt = user_interrupt_flag.is_set()
                if not did_user_interrupt:
                    put_on_print_queue(filepath, lines_found)
                else:
                    continue_thread = False
        else:
            continue_thread = False


def list_files_to_check(file_folder, extensions):
    """List files to search

    Args:
        file_folder (str): File/folder
        extensions (str): List of extensions (comma-separated) for freeplane files
    Returns:
        list: List of file paths (str) to search from file/folder

    """
    files_to_search = []
    map_extensions = extensions.split(",")
    if os.path.isfile(file_folder):
        files_to_search.append(file_folder)
    elif os.path.isdir(file_folder):
        for dp, _, files in os.walk(file_folder):
            for f in files:
                if any([f.endswith(e) for e in map_extensions ]):
                    full_path = os.path.join(dp, f)
                    files_to_search.append(full_path)
    else:
        error(f"Unknown file path: {file_folder}")

    return files_to_search

def launch_all_threads(file_folder, keywords, delimiter, case_sensitive, extensions, num_threads,
    replace_newlines, validate_only=False):
    """
    Launch all the threads that will perform the search across the various Freeplane Map files

    Args:
        file_folder (str): Path to file/folder 
        keywords (str): Regex keywords to search
        delimiter (str): Delimiter to use for multiple keywords
        case_sensitive (bool): Case sensitive
        extensions (str): List of freeplane file extensions
        num_threads (int): Number of threads for search tasks
        replace_new_lines (bool): Replace new lines
        validate_only (bool, optional): Validate mindmap only. Defaults, False.
    """

    files_to_search = list_files_to_check(file_folder, extensions)

    thread_objects = []

    # Launch the threads to open map and search
    for _ in range(0, num_threads):
        t = threading.Thread(target=open_map_and_search, args=(keywords, delimiter, case_sensitive,
            replace_newlines, validate_only))
        t.start()   
        thread_objects.append(t)

    # Launch the search threads
    for fp in files_to_search:
        put_search_tasks(fp)

    # Launch the thread to print the task

    t = threading.Thread(target=print_matches)
    t.start()
    thread_objects.append(t)

    # Join all the threads to the main thread
    for t in thread_objects:
        t.join()


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=CustomFormatter)
    parser.add_argument("-k", "--keywords", required=True, 
        help=("One or multiple Keyword search (or regex) in Freeplane files. "
              "Repeat this argument to supply multiple values"))
    parser.add_argument("-d", "--delimiter", default=" ", 
        help="Delimiter to use for multiple keywords")
    parser.add_argument("-f", "--file-folder", default="/opt/my-maps", help="File/folder to search")
    parser.add_argument("-c", "--case-sensitive", action="store_true", 
        help="Keyword search (regex) in the Freeplane files")
    parser.add_argument("-nt", "--num-threads", default=10, 
        help="Number of threads to use to search for strings")
    parser.add_argument("-e", "--extensions", default=FREEPLANE_MAPS_EXTENSIONS, 
        help="Freeplane Map file extensions to use for searching freeplanes")
    parser.add_argument("-v", "--verbose", action="store_true",
        help="Verbose to print messages")
    parser.add_argument("-rn", "--replace-newlines", action="store_true", 
        help="Replace new lines with '\\n' to allow printing of matches per line")
    parser.add_argument("-va", "--validate", action="store_true", 
        help="Validate the mindmaps only")

    args = parser.parse_args()

    if args.verbose:
        global verbose_flag
        verbose_flag = True

    init_print_queue()
    
    init_search_tasks_queue()

    launch_all_threads(args.file_folder, args.keywords, args.delimiter, args.case_sensitive, 
        args.extensions, int(args.num_threads), args.replace_newlines, args.validate)

if __name__ == "__main__":
    sys.exit(main())

