import os
import re

import numpy as np
import torch
from torchtext.data import NestedField, Field, TabularDataset
from torchtext.data.iterator import BucketIterator
from torchtext.vocab import Vectors


def clean_string(string):
    """
    Performs tokenization and string cleaning for the Lyrics dataset
    """
    string = re.sub(r"[^A-Za-z0-9(),!?\'`]", " ", string)
    string = re.sub(r"\s{2,}", " ", string)
    return string.lower().strip().split()


def split_sents(string):
    string = re.sub(r"[!?]"," ", string)
    return string.strip().split('.')


def char_quantize(string, max_length=1000):
    identity = np.identity(len(LyricsArtistCharQuantized.ALPHABET))
    quantized_string = np.array([identity[LyricsArtistCharQuantized.ALPHABET[char]] for char in list(string.lower()) if char in LyricsArtistCharQuantized.ALPHABET], dtype=np.float32)
    if len(quantized_string) > max_length:
        return quantized_string[:max_length]
    else:
        return np.concatenate((quantized_string, np.zeros((max_length - len(quantized_string), len(LyricsArtistCharQuantized.ALPHABET)), dtype=np.float32)))


def process_labels(string):
    """
    Returns the label string as a list of integers
    :param string:
    :return:
    """
    return [float(x) for x in string]


class LyricsArtist(TabularDataset):
    # NAME = 'LyricsArtist'
    # NUM_CLASSES = 100
    # IS_MULTILABEL = True

    TEXT_FIELD = Field(batch_first=True, tokenize=clean_string, include_lengths=True)
    LABEL_FIELD = Field(sequential=False, use_vocab=False, batch_first=True, preprocessing=process_labels)
    NAME = 'LyricsArtist'

    def set_attributes(self, data_dir):
        # self.NAME = 'LyricsGenre'
        # self.TEXT_FIELD = Field(batch_first=True, tokenize=clean_string, include_lengths=True)
        # self.LABEL_FIELD = Field(sequential=False, use_vocab=False, batch_first=True, preprocessing=process_labels)

        with open(os.path.join(data_dir, 'LyricsArtist', 'train.tsv'), 'r') as f:
            l1 = f.readline().split('\t')

        # from one-hot class vector
        self.NUM_CLASSES = len(l1[0])
        self.IS_MULTILABEL = self.NUM_CLASSES > 2

    @staticmethod
    def sort_key(ex):
        return len(ex.text)

    @classmethod
    def splits(cls, path, train=os.path.join('LyricsArtist', 'train.tsv'),
               validation=os.path.join('LyricsArtist', 'dev.tsv'),
               test=os.path.join('LyricsArtist', 'test.tsv'), **kwargs):
        return super(LyricsArtist, cls).splits(
            path, train=train, validation=validation, test=test,
            format='tsv', fields=[('label', cls.LABEL_FIELD), ('text', cls.TEXT_FIELD)]
        )

    @classmethod
    def iters(cls, path, vectors_name, vectors_cache, batch_size=64, shuffle=True, device=0, vectors=None,
              unk_init=torch.Tensor.zero_):
        """
        :param path: directory containing train, test, dev files
        :param vectors_name: name of word vectors file
        :param vectors_cache: path to directory containing word vectors file
        :param batch_size: batch size
        :param device: GPU device
        :param vectors: custom vectors - either predefined torchtext vectors or your own custom Vector classes
        :param unk_init: function used to generate vector for OOV words
        :return:
        """
        if vectors is None:
            vectors = Vectors(name=vectors_name, cache=vectors_cache, unk_init=unk_init)

        train, val, test = cls.splits(path)
        cls.TEXT_FIELD.build_vocab(train, val, test, vectors=vectors)
        return BucketIterator.splits((train, val, test), batch_size=batch_size, repeat=False, shuffle=shuffle,
                                     sort_within_batch=True, device=device)


class LyricsArtistCharQuantized(LyricsArtist):
    ALPHABET = dict(map(lambda t: (t[1], t[0]), enumerate(list("""abcdefghijklmnopqrstuvwxyz0123456789,;.!?:'\"/\\|_@#$%^&*~`+-=<>()[]{}"""))))
    TEXT_FIELD = Field(sequential=False, use_vocab=False, batch_first=True, preprocessing=char_quantize)

    @classmethod
    def iters(cls, path, vectors_name, vectors_cache, batch_size=64, shuffle=True, device=0, vectors=None,
              unk_init=torch.Tensor.zero_):
        """
        :param path: directory containing train, test, dev files
        :param batch_size: batch size
        :param device: GPU device
        :return:
        """
        train, val, test = cls.splits(path)
        return BucketIterator.splits((train, val, test), batch_size=batch_size, repeat=False, shuffle=shuffle, device=device)


class LyricsArtistHierarchical(LyricsArtist):
    NESTING_FIELD = Field(batch_first=True, tokenize=clean_string)
    TEXT_FIELD = NestedField(NESTING_FIELD, tokenize=split_sents)
