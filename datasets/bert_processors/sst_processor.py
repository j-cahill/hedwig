import os

from datasets.bert_processors.abstract_processor import BertProcessor, InputExample


class SST2Processor(BertProcessor):
    def __init__(self):
        self.NAME = 'SST-2'

    def set_num_classes_(self, data_dir):
        with open(os.path.join(data_dir, 'SST-2', 'train.tsv'), 'r') as f:
            l1 = f.readline().split('\t')

        # from one-hot class vector
        self.NUM_CLASSES = len(l1[0])
        self.IS_MULTILABEL = self.NUM_CLASSES > 2

    def get_train_examples(self, data_dir):
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'SST-2', 'train.tsv')), 'train')

    def get_dev_examples(self, data_dir):
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'SST-2', 'dev.tsv')), 'dev')

    def get_test_examples(self, data_dir):
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'SST-2', 'test.tsv')), 'test')

    @staticmethod
    def _create_examples(lines, set_type):
        """
        Creates examples for the training and dev sets
        :param lines:
        :param set_type:
        :return:
        """
        examples = []
        for (i, line) in enumerate(lines):
            if i == 0:
                continue
            guid = '%s-%s' % (set_type, i)
            label = line[0]
            text = line[1]
            examples.append(InputExample(guid=guid, text_a=text, text_b=None, label=label))
        return examples
