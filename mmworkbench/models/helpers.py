# -*- coding: utf-8 -*-
"""This module contains some helper functions for the models package"""
from __future__ import unicode_literals
from sklearn.metrics import make_scorer

import re
import copy

from ..gazetteer import Gazetteer

FEATURE_MAP = {}
MODEL_MAP = {}
LABEL_MAP = {}

# Example types
QUERY_EXAMPLE_TYPE = 'query'
ENTITY_EXAMPLE_TYPE = 'entity'

# Label types
CLASS_LABEL_TYPE = 'class'
ENTITIES_LABEL_TYPE = 'entities'


# resource/requirements names
GAZETTEER_RSC = 'gazetteers'
QUERY_FREQ_RSC = 'q_freq'
SYS_TYPES_RSC = 'sys_types'
WORD_FREQ_RSC = 'w_freq'
WORD_NGRAM_FREQ_RSC = 'w_ngram_freq'
CHAR_NGRAM_FREQ_RSC = 'c_ngram_freq'
OUT_OF_BOUNDS_TOKEN = '<$>'


def create_model(config):
    """Creates a model instance using the provided configuration

    Args:
        config (ModelConfig): A model configuration

    Returns:
        Model: a configured model

    Raises:
        ValueError: When model configuration is invalid
    """
    try:
        return MODEL_MAP[config.model_type](config)
    except KeyError:
        msg = 'Invalid model configuration: Unknown model type {!r}'
        raise ValueError(msg.format(config.model_type))


def get_feature_extractor(example_type, name):
    """Gets a feature extractor given the example type and name

    Args:
        example_type (str): The type of example
        name (str): The name of the feature extractor

    Returns:
        function: A feature extractor wrapper
    """
    return FEATURE_MAP[example_type][name]


def get_label_encoder(config):
    """Gets a label encoder given the label type from the config

    Args:
        config (ModelConfig): A model configuration

    Returns:
        LabelEncoder: The appropriate LabelEncoder object for the given config
    """
    return LABEL_MAP[config.label_type](config)


def register_model(model_type, model_class):
    """Registers a model for use with `create_model()`

    Args:
        model_type (str): The model type as specified in model configs
        model_class (class): The model to register
    """
    if model_type in MODEL_MAP:
        raise ValueError('Model {!r} is already registered.'.format(model_type))

    MODEL_MAP[model_type] = model_class


def register_features(example_type, features):
    """Register a set of feature extractors for use with
    `get_feature_extractor()`

    Args:
        example_type (str): The example type of the feature extractors
        features (dict): Features extractor templates keyed by name

    Raises:
        ValueError: If the example type is already registered
    """
    if example_type in FEATURE_MAP:
        msg = 'Features for example type {!r} are already registered.'.format(example_type)
        raise ValueError(msg)

    FEATURE_MAP[example_type] = features


def register_label(label_type, label_encoder):
    """Register a label encoder for use with
    `get_label_encoder()`

    Args:
        label_type (str): The label type of the label encoder
        label_encoder (LabelEncoder): The label encoder class to register

    Raises:
        ValueError: If the label type is already registered
    """
    if label_type in LABEL_MAP:
        msg = 'Label encoder for label type {!r} is already registered.'.format(label_type)
        raise ValueError(msg)

    LABEL_MAP[label_type] = label_encoder


def mask_numerics(token):
    """Masks digit characters in a token"""
    if token.isdigit():
        return '#NUM'
    else:
        return re.sub(r'\d', '8', token)


def get_ngram(tokens, start, length):
    """Gets a ngram from a list of tokens.

    Handles out-of-bounds token positions with a special character.

    Args:
        tokens (list of str): Word tokens.
        start (int): The index of the desired ngram's start position.
        length (int): The length of the n-gram, e.g. 1 for unigram, etc.

    Returns:
        (str) An n-gram in the input token list.
    """

    ngram_tokens = []
    for index in range(start, start+length):
        token = (OUT_OF_BOUNDS_TOKEN if index < 0 or index >= len(tokens)
                 else tokens[index])
        ngram_tokens.append(token)
    return ' '.join(ngram_tokens)


def get_seq_accuracy_scorer():
    """
    Returns a scorer that can be used by sklearn's GridSearchCV based on the
    sequence_accuracy_scoring method below.
    """
    return make_scorer(score_func=sequence_accuracy_scoring)


def get_seq_tag_accuracy_scorer():
    """
    Returns a scorer that can be used by sklearn's GridSearchCV based on the
    sequence_tag_accuracy_scoring method below.
    """
    return make_scorer(score_func=sequence_tag_accuracy_scoring)


def sequence_accuracy_scoring(y_true, y_pred):
    """
    Accuracy score which calculates two sequences to be equal only if all of
    their predicted tags are equal.
    """
    total = len(y_true)
    if not total:
        return 0

    matches = sum(1 for yseq_true, yseq_pred in zip(y_true, y_pred)
                  if yseq_true == yseq_pred)

    return float(matches) / float(total)


def sequence_tag_accuracy_scoring(y_true, y_pred):
    """
    Accuracy score which calculates the number of tags that were predicted
    correctly.
    """
    y_true_flat = [tag for seq in y_true for tag in seq]
    y_pred_flat = [tag for seq in y_pred for tag in seq]

    total = len(y_true_flat)
    if not total:
        return 0

    matches = sum(1 for (y_true_tag, y_pred_tag) in zip(y_true_flat, y_pred_flat)
                  if y_true_tag == y_pred_tag)

    return float(matches) / float(total)


def entity_seqs_equal(expected, predicted):
    """
    Returns true if the expected entities and predicted entities all match, returns
    false otherwise. Note that for entity comparison, we compare that the span, text,
    and type of all the entities match.

    Args:
        expected (list of core.Entity): A list of the expected entities for some query
        predicted (list of core.Entity): A list of the predicted entities for some query
    """
    if len(expected) != len(predicted):
        return False
    for expected_entity, predicted_entity in zip(expected, predicted):
        if expected_entity.entity.type != predicted_entity.entity.type:
            return False
        if expected_entity.span != predicted_entity.span:
            return False
        if expected_entity.text != predicted_entity.text:
            return False
    return True


def ingest_dynamic_gazetteer(resource, dynamic_resource=None):
    """Ingests dynamic gazetteers from the app and adds them to the resource

    Args:
        resource (dict): The original resource
        dynamic_resource (dict, optional): The dynamic resource that needs to be ingested

    Returns:
        (dict): A new resource with the ingested dynamic resource
    """
    workspace_resource = copy.deepcopy(resource)
    if dynamic_resource and GAZETTEER_RSC in dynamic_resource:
        for entity in dynamic_resource[GAZETTEER_RSC]:
            if entity in workspace_resource[GAZETTEER_RSC]:
                new_gaz = Gazetteer(entity)
                new_gaz.from_dict(workspace_resource[GAZETTEER_RSC][entity])
                if workspace_resource[GAZETTEER_RSC][entity]['total_entities'] > 0:
                    for key in dynamic_resource[GAZETTEER_RSC][entity]:
                        new_gaz._update_entity(key, dynamic_resource[GAZETTEER_RSC][entity][key])
                workspace_resource[GAZETTEER_RSC][entity] = new_gaz.to_dict()
    return workspace_resource


def requires(resource):
    """
    Decorator to enforce the resource dependencies of the active feature extractors

    Args:
        resource (str): the key of a classifier resource which must be initialized before
            the given feature extractor is used

    Returns:
        (func): the feature extractor
    """
    def add_resource(func):
        req = func.__dict__.get('requirements', set())
        req.add(resource)
        func.requirements = req
        return func

    return add_resource
