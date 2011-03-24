#!/usr/bin/env python
#-*- coding:utf-8 -*-
# ---------------------------------------------------------------
# xortool.py
#   A tool to do some xor analysis:
#   - guess the key length (based on count of equal chars)
#   - guess the key (base on knowledge of most frequent char)
# Usage:
#   xortool [-h|--help] [OPTIONS] [<filename>]
# Options:
#   -l,--key-length     length of the key
#   -c,--char           most frequent char
#   -x,--hex            input is hex-encoded str
#   -m,--max-keylen     maximum key length to probe
# Examples:
#   xortool file.bin
#   xortool -x -l 4 -c ' ' file.hex
# ---------------------------------------------------------------
# Author: hellman ( hellman1908@gmail.com )
# ---------------------------------------------------------------

import os
import sys
import math

from routine import *
from args import parse_parameters

DIRNAME = 'xortool'  # here plaintexts will be placed
PARAMETERS = dict()

def main():
    global PARAMETERS
    PARAMETERS = parse_parameters()
    
    ciphertext = get_ciphertext()
    
    update_key_length(ciphertext)

    probable_keys = guess_probable_keys(ciphertext)
    print_keys(probable_keys)
    
    produce_plaintexts(ciphertext, probable_keys)
    return

# ------------------------------------------------------------------------------
# LOADING CIPHERTEXT
# ------------------------------------------------------------------------------

def get_ciphertext():
    """
    Load ciphertext from a file or stdin and hex-decode if needed
    """
    ciphertext = load_file(PARAMETERS["filename"])
    if PARAMETERS["input_is_hex"]:
        ciphertext = decode_from_hex(ciphertext)
    return ciphertext

# ------------------------------------------------------------------------------
# KEYLENGTH GUESSING SECTION
# ------------------------------------------------------------------------------

def update_key_length(text):
    """
    Guess length of the key if it's not set. (Updates PARAMETERS)
    """
    global PARAMETERS
    if PARAMETERS["known_key_length"]:
        return
    PARAMETERS["known_key_length"] = guess_key_length(text)
    return


def guess_key_length(text):
    """
    Try key lengths from 1 to max_key_length and print local maximums.
    Set key_length to the most possible if it's not set by user.
    """
    fitnesses = calculate_fitnesses(text)
    print_fitnesses(fitnesses)
    guess_and_print_divizors(fitnesses)
    
    return get_max_fitnessed_key_length(fitnesses)


def calculate_fitnesses(text):
    """
    Calc. fitnesses for each keylen
    """
    prev = 0
    pprev = 0
    fitnesses = []
    for key_length in range(1, PARAMETERS["max_key_length"]+1):
        fitness = count_equals(text, key_length)
        fitness = float(fitness)/(64 + key_length**0.5)
        
        if pprev < prev and prev > fitness:  # local maximum
            fitnesses += [(key_length-1, prev)]

        pprev = prev
        prev = fitness
    
    return fitnesses


def print_fitnesses(fitnesses):
    print "Probable key lengths:"
    fitness_sum = calculate_fitness_sum(fitnesses)
    for key_length, fitness in fitnesses:
        print str(key_length).rjust(4," ") + ":  ",
        print round(100 * fitness * 1.0 / fitness_sum, 1), "%"
    return


def calculate_fitness_sum(fitnesses):
    return sum([f for (key_length, f) in fitnesses])


def count_equals(text, key_length):
    """
    count equal chars count for each offset and sum them
    """
    equals_count = 0
    if key_length >= len(text):
        return 0
        
    for offset in range(key_length):
        chars_count = chars_count_at_offset(text, key_length, offset)
        equals_count += max(chars_count.values())-1  # why -1? don't know
    return equals_count


def guess_and_print_divizors(fitnesses):
    """
    Prints common divizors and returns the most common divizor
    """
    divizors_counts = [ 0 for i in range(PARAMETERS["max_key_length"]+1) ]
    for key_length, fitness in fitnesses:
        for number in range(3, key_length+1):
            if key_length % number == 0:
                divizors_counts[number] += 1
    max_divizors = max(divizors_counts)
    
    ret = 2
    for number, divizors_count in enumerate(divizors_counts):
        if divizors_count == max_divizors:
            print "Key-length can be " + str(number) + "*n"
            ret = number
    return ret


def get_max_fitnessed_key_length(fitnesses):
    max_fitness = 0
    max_fitnessed_key_length = 0
    for key_length, fitness in fitnesses:
        if fitness > max_fitness:
            max_fitness = fitness
            max_fitnessed_key_length = key_length
    return max_fitnessed_key_length


def chars_count_at_offset(text, key_length, offset):
    chars_count = dict()
    for pos in range(offset, len(text), key_length):
        c = text[pos]
        if c in chars_count:
            chars_count[c] += 1
        else:
            chars_count[c] = 1
    return chars_count

# ------------------------------------------------------------------------------
# KEYS GUESSING SECTION
# ------------------------------------------------------------------------------

def guess_probable_keys(text):
    """
    Guess key if the most frequent char is known.
    """
    probable_keys = []
    if PARAMETERS["most_frequent_char"] is None:
        die("Most possible char is needed to guess the key!")
    else:
        probable_keys = guess_keys(text)
    return probable_keys


def guess_keys(text):
    """
    Generate all possible keys for key length 
    and the most possible char     
    """
    key_length = PARAMETERS["known_key_length"]
    most_char = PARAMETERS["most_frequent_char"]
    key_possible_bytes = [[] for i in range(key_length)]

    for offset in range(key_length):  #each byte of key<
        chars_count = chars_count_at_offset(text, key_length, offset)
        max_count = max(chars_count.values())
        for char in chars_count:
            if chars_count[char] >= max_count:
                key_possible_bytes[offset] += chr(ord(char) ^ most_char)

    return all_keys(key_possible_bytes)


def all_keys(key_possible_bytes, key_part="", offset=0):
    """
    Produce all combinations of possible key chars
    """
    keys = []
    if offset >= len(key_possible_bytes):
        return [key_part]
    for c in key_possible_bytes[offset]:
        keys += all_keys(key_possible_bytes, key_part + c, offset+1)
    return keys


def print_keys(keys):
    if not keys:
        print "No keys guessed!"
        return
    print "{0} possible key(s) of length {1}:".format(len(keys), len(keys[0]))
    for key in keys[:5]:
        print repr(key)[1:-1]
    if len(keys) > 10:
        print "..."

# ------------------------------------------------------------------------------
# PRODUCE OUTPUT
# ------------------------------------------------------------------------------

def produce_plaintexts(ciphertext, keys):
    """
    Produce plaintext variant for each possible key
    """
    if os.path.exists(DIRNAME):
        rmdir(DIRNAME)
    mkdir(DIRNAME)
    
    for index, key in enumerate(keys):
        key_index = str(index).rjust(len(str(len(keys) - 1)), "0")
        key_repr = repr(key)[1:-1].replace("/", "\\x2f")
        if not is_linux():
            key_repr = alphanum(key)
        file_name = os.path.join("xortool", key_index + "_" + key_repr)
        f = open(file_name, "wb")
        f.write(dexor(ciphertext, key))
        f.close()
    return


if __name__ == "__main__":
    main()
