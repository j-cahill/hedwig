import warnings

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn import metrics
from torch.utils.data import DataLoader, SequentialSampler, TensorDataset
from tqdm import tqdm

from datasets.bert_processors.abstract_processor import convert_examples_to_features, \
    convert_examples_to_hierarchical_features
from utils.preprocessing import pad_input_matrix
from utils.tokenization import BertTokenizer

# Suppress warnings from sklearn.metrics
warnings.filterwarnings('ignore')


class BertEvaluator(object):
    def __init__(self, model, processor, args, split='dev'):
        self.args = args
        self.model = model
        self.processor = processor
        self.tokenizer = BertTokenizer.from_pretrained(args.model, is_lowercase=args.is_lowercase)
        if split == 'test':
            self.eval_examples = self.processor.get_test_examples(args.data_dir)
        else:
            self.eval_examples = self.processor.get_dev_examples(args.data_dir)

    def get_scores(self, silent=False):
        if self.args.is_hierarchical:
            eval_features = convert_examples_to_hierarchical_features(
                self.eval_examples, self.args.max_seq_length, self.tokenizer)
        else:
            eval_features = convert_examples_to_features(
                self.eval_examples, self.args.max_seq_length, self.tokenizer)

        unpadded_input_ids = [f.input_ids for f in eval_features]
        unpadded_input_mask = [f.input_mask for f in eval_features]
        unpadded_segment_ids = [f.segment_ids for f in eval_features]

        if self.args.is_hierarchical:
            pad_input_matrix(unpadded_input_ids, self.args.max_doc_length)
            pad_input_matrix(unpadded_input_mask, self.args.max_doc_length)
            pad_input_matrix(unpadded_segment_ids, self.args.max_doc_length)

        padded_input_ids = torch.tensor(unpadded_input_ids, dtype=torch.long)
        padded_input_mask = torch.tensor(unpadded_input_mask, dtype=torch.long)
        padded_segment_ids = torch.tensor(unpadded_segment_ids, dtype=torch.long)
        label_ids = torch.tensor([f.label_id for f in eval_features], dtype=torch.long)

        eval_data = TensorDataset(padded_input_ids, padded_input_mask, padded_segment_ids, label_ids)
        eval_sampler = SequentialSampler(eval_data)
        eval_dataloader = DataLoader(eval_data, sampler=eval_sampler, batch_size=self.args.batch_size)

        self.model.eval()

        total_loss = 0
        nb_eval_steps, nb_eval_examples = 0, 0
        predicted_labels, target_labels = list(), list()

        for input_ids, input_mask, segment_ids, label_ids in tqdm(eval_dataloader, desc="Evaluating", disable=silent):
            input_ids = input_ids.to(self.args.device)
            input_mask = input_mask.to(self.args.device)
            segment_ids = segment_ids.to(self.args.device)
            label_ids = label_ids.to(self.args.device)

            with torch.no_grad():
                logits = self.model(input_ids, segment_ids, input_mask)

            if self.args.is_multilabel:
                predicted_labels.extend(F.softmax(logits, dim=1).cpu().detach().numpy())
                # print(F.softmax(logits).cpu().detach().numpy())
                target_labels.extend(label_ids.cpu().detach().numpy())
                loss = F.binary_cross_entropy_with_logits(logits, label_ids.float(), size_average=False)
            else:
                predicted_labels.extend(torch.argmax(logits, dim=1).cpu().detach().numpy())
                target_labels.extend(torch.argmax(label_ids, dim=1).cpu().detach().numpy())
                loss = F.cross_entropy(logits, torch.argmax(label_ids, dim=1))

            if self.args.n_gpu > 1:
                loss = loss.mean()
            if self.args.gradient_accumulation_steps > 1:
                loss = loss / self.args.gradient_accumulation_steps
            total_loss += loss.item()

            nb_eval_examples += input_ids.size(0)
            nb_eval_steps += 1

        if self.args.is_multilabel:
            score_method = 'weighted'
            pos_label = None
        else:
            score_method = 'binary'
            pos_label = 1

        # np.savetxt('predicted_untransformed.csv', predicted_labels, delimiter=',')
        predicted_labels, target_labels = np.array(predicted_labels), np.array(target_labels)
        predicted_labels = (predicted_labels == predicted_labels.max(axis=1, keepdims=True)).astype(int)

        accuracy = metrics.accuracy_score(target_labels, predicted_labels)
        precision = metrics.precision_score(target_labels, predicted_labels, average=score_method, pos_label=pos_label)
        recall = metrics.recall_score(target_labels, predicted_labels, average=score_method, pos_label=pos_label)
        f1 = metrics.f1_score(target_labels, predicted_labels, average=score_method, pos_label=pos_label)
        avg_loss = total_loss / nb_eval_steps

        predicted_labels = np.apply_along_axis(lambda x: ''.join(x), 1, predicted_labels.astype(str))
        target_labels = np.apply_along_axis(lambda x: ''.join(x), 1, target_labels.astype(str))
        # predictions = np.hstack([predicted_labels, target_labels])

        # np.savetxt('predictions.csv', predictions, delimiter=',')
        x = np.random.randint(1000)
        with open('predictions_{}.txt'.format(x), 'w') as f:
            pred = pd.DataFrame(
                {
                    'predicted': predicted_labels,
                    'target': target_labels
                }
            )
            pred.to_csv(f)

        return [accuracy, precision, recall, f1, avg_loss], ['accuracy', 'precision', 'recall', 'f1', 'avg_loss']
