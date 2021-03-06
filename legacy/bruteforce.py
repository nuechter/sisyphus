#!/usr/bin/env python
#
# Copyright 2012 Johannes 'josch' Schauer <j.schauer@email.de>
#
# This file is part of Sisyphus.
#
# Sisyphus is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sisyphus is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sisyphus.  If not, see <http://www.gnu.org/licenses/>.

# 1. layered approach
#
#     options for layers of equal height:
#         sort by: area, max(length, width), weight
#         articles rotated: 0, 1
#         pallet rotated: 90, 180, 270
#     => 18 possible configurations per layer
#     18^n layer sets (18, 324, 5832, 104976)
#
# 2. free 3d packing

import sys
import subprocess
import itertools
import shutil
from util import xmlfiletodict, dicttoxmlfile, get_pallet, get_articles, get_packlist_dict

if len(sys.argv) != 3:
    print "usage:", sys.argv[0], "order.xml packlist.xml"
    exit(0)

orderline = xmlfiletodict(sys.argv[1])

pallet = get_pallet(orderline)

articles = get_articles(orderline)

# bins of items of equal height
bins = dict()

for article in articles:
    abin = bins.get(article['Article']['Height'])
    if abin:
        abin.append(article)
    else:
        bins[article['Article']['Height']] = [article]

def arrange_in_layer(abin, plength, pwidth):
    # articles are longer than wider
    # default rotation: length: x-direction
    #                   width:  y-direction

    layer = list()
    rest = list()
    root = {'x': 0, 'y': 0, 'length': plength, 'width': pwidth, 'used': False, 'up': None, 'right': None}

    def find_node(root, length, width):
        if root['used']:
            return find_node(root['right'], length, width) or find_node(root['up'], length, width)
        elif length <= root['length'] and width <= root['width']:
            return root
        else:
            return None

    def split_node(node, length, width):
        node['used'] = True
        node['up'] =    {'x': node['x'], 'y': node['y']+width, 'length': node['length'], 'width': node['width']-width, 'used': None, 'up': None, 'right': None}
        node['right'] = {'x': node['x']+length, 'y': node['y'], 'length': node['length']-length, 'width': width, 'used': None, 'up': None, 'right': None}
        return node

    for article in abin:
        # output format only accepts integer positions, round package sizes up to even numbers
        length, width = (article['Article']['Length'], article['Article']['Width'])
        if length%2 != 0:
            length += 1
        if width%2 != 0:
            width +=1

        node = find_node(root, length, width)
        if (node):
            node = split_node(node, length, width)
            article['PlacePosition']['X'] = node['x']+length/2
            article['PlacePosition']['Y'] = node['y']+width/2
            layer.append(article)
        else:
            # TODO: try again with article rotated
            # print "didnt fit"
            rest.append(article)

    return layer, rest


# list of lists of layers
# each list of layers was generated by a different approach
list_of_layerlists = list()

plength, pwidth = (pallet['Dimensions']['Length'], pallet['Dimensions']['Width'])

import copy

def process(to_be_processed_bins, current_bin=None, layers=[]):
    if not current_bin:
        if not to_be_processed_bins:
            list_of_layerlists.append(layers)
            return
        current_bin = to_be_processed_bins.pop()
    abin = sorted(current_bin, key=lambda article: article['Article']['Length']*article['Article']['Width'], reverse=True)
    layer, rest = arrange_in_layer(abin, plength, pwidth)
    if layer:
        l1 = copy.deepcopy(layers)
        l1.append(layer)
        process(copy.deepcopy(to_be_processed_bins), copy.deepcopy(rest), l1)
    else:
        if rest:
            rests.append(rest)
        process(copy.deepcopy(to_be_processed_bins), None, copy.deepcopy(layers))

    abin = sorted(current_bin, key=lambda article: article['Article']['Weight'], reverse=True)
    layer, rest = arrange_in_layer(abin, plength, pwidth)
    if layer:
        l2 = copy.deepcopy(layers)
        l2.append(layer)
        process(copy.deepcopy(to_be_processed_bins), copy.deepcopy(rest), l2)
    else:
        if rest:
            rests.append(rest)
        process(copy.deepcopy(to_be_processed_bins), None, copy.deepcopy(layers))

process(bins.values())

"""
for layers in list_of_layerlists:
    print len(layers)
print len(list_of_layerlists)
exit()
"""

"""
for abin in bins:
    # TODO: sort by something different and see what gives better result
    # TODO: try to rotate result 180 degrees
    # TODO: try to build with pallet rotated 90 or 270 degrees
    # TODO: try to rotate boxes by 90 degrees beforehand
    # TODO: check if articles from to-be-processed bins fits inbetween current layer articles
    # TODO: divide pallet horizontally, vertically and both and fill parts equally and connect afterwards
    bins[abin] = sorted(bins[abin], key=lambda article: article['Article']['Length']*article['Article']['Width'], reverse=True)
    plength, pwidth = (pallet['Dimensions']['Length'], pallet['Dimensions']['Width'])
    layer, rest = arrange_in_layer(bins[abin], plength, pwidth)
    while layer:
        occupied_area = 0
        for article in layer:
            length, width = article['Article']['Length'], article['Article']['Width']
            occupied_area += length*width

        # print "layer occupation:", occupied_area/float(plength*pwidth)
        if occupied_area/float(plength*pwidth) <= 0.7:
            rests.append(layer)
        else:
            layers.append(layer)

        layer, rest = arrange_in_layer(rest, plength, pwidth)

    #if rest:
    #    rests.append(rest)
"""

# TODO: care for possible rests

# TODO: enumerate all possible combinations of layers

score_max = 0.0

import copy

for layers in list_of_layerlists:
    for layer_order in itertools.permutations(layers):
        pack_sequence = 1
        pack_height = 0
        articles_to_pack = list()

        for layer in layer_order:
            pack_height += layer[0]['Article']['Height']
            for article in layer:
                article['PackSequence'] = pack_sequence
                article['PlacePosition']['Z'] = pack_height
                articles_to_pack.append(article)
                pack_sequence += 1

        dicttoxmlfile(get_packlist_dict(pallet, articles_to_pack), sys.argv[2]+".tmp")

        score = float(subprocess.check_output("../palletandtruckviewer-3.0/palletViewer -o "
            +sys.argv[1]+" -p "+sys.argv[2]
            +".tmp -s ../icra2011TestFiles/scoreAsPlannedConfig1.xml --headless | grep Score", shell=True).split(' ')[1].strip())
        print score
        if score > score_max:
            shutil.move(sys.argv[2]+".tmp", sys.argv[2])
