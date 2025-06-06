# -*- coding: utf-8 -*-
"""PalomaAlves_Notebook_token_classification_NER_BERT_base.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1MwpQSwlboy7kUJHStRNSBwwItzHXPjUH

# Reconhecimento de Entidades Nomeadas no Contexto Jurídico Utilizando Redes Neurais

## Visão geral

1- Objetivo do Projeto:

Desenvolver e implementar um modelo de Reconhecimento de Entidades Nomeadas (Named Entity Recognition - NER) aplicado ao domínio jurídico, com foco em legislações e documentos legais, e avaliar a precisão dos modelos. O projeto visa simplificar a extração de informações relevantes em textos complexos e extensos, facilitando a análise jurídica.

## Configuração
"""

task = "ner" # Should be one of "ner", "pos" or "chunk"

model_checkpoint = "Palu1006/ner-bert-lenerbr-v2"

from google.colab import drive
drive.mount('/content/drive', force_remount=True)

"""Se você estiver abrindo este Notebook no colab, provavelmente precisará instalar 🤗 Transformers e 🤗 Datasets. Remova o comentário da célula a seguir e execute-a."""

!pip install datasets seqeval

!pip install -U accelerate
!pip install -U transformers

!apt install git-lfs

import transformers

print(transformers.__version__)

import datasets

print(datasets.__version__)

import pathlib
from pathlib import Path

import pandas as pd

from datasets import Dataset, DatasetDict

"""## Carregando o conjunto de dados"""

!pip install evaluate
from datasets import load_dataset

datasets = load_dataset("lener_br", trust_remote_code=True)

datasets

datasets["train"][0]

datasets["train"].features[f"ner_tags"]

label_list = datasets["train"].features[f"{task}_tags"].feature.names
label_list

from datasets import ClassLabel, Sequence
import random
import pandas as pd
from IPython.display import display, HTML

def show_random_elements(dataset, num_examples=10):
    assert num_examples <= len(dataset), "Can't pick more elements than there are in the dataset."
    picks = []
    for _ in range(num_examples):
        pick = random.randint(0, len(dataset)-1)
        while pick in picks:
            pick = random.randint(0, len(dataset)-1)
        picks.append(pick)

    df = pd.DataFrame(dataset[picks])
    for column, typ in dataset.features.items():
        if isinstance(typ, ClassLabel):
            df[column] = df[column].transform(lambda i: typ.names[i])
        elif isinstance(typ, Sequence) and isinstance(typ.feature, ClassLabel):
            df[column] = df[column].transform(lambda x: [typ.feature.names[i] for i in x])
    display(HTML(df.to_html()))

show_random_elements(datasets["train"])

"""##Pré-processando os dados"""

from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)

import transformers
assert isinstance(tokenizer, transformers.PreTrainedTokenizerFast)

tokenizer("Hello, this is one sentence!")

tokenizer(["Hello", ",", "this", "is", "one", "sentence", "split", "into", "words", "."], is_split_into_words=True)

example = datasets["train"][5]
print(example["tokens"])

tokenized_input = tokenizer(example["tokens"], is_split_into_words=True)
tokens = tokenizer.convert_ids_to_tokens(tokenized_input["input_ids"])
print(tokens)

len(example[f"{task}_tags"]), len(tokenized_input["input_ids"])

print(tokenized_input.word_ids())

word_ids = tokenized_input.word_ids()
aligned_labels = [-100 if i is None else example[f"{task}_tags"][i] for i in word_ids]
print(len(aligned_labels), len(tokenized_input["input_ids"]))

label_all_tokens = True

def tokenize_and_align_labels(examples):
    tokenized_inputs = tokenizer(examples["tokens"], truncation=True, is_split_into_words=True, max_length=512, padding='max_length')

    labels = []
    for i, label in enumerate(examples[f"{task}_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            # Special tokens have a word id that is None. We set the label to -100 so they are automatically
            # ignored in the loss function.
            if word_idx is None:
                label_ids.append(-100)
            # We set the label for the first token of each word.
            elif word_idx != previous_word_idx:
                label_ids.append(label[word_idx])
            # For the other tokens in a word, we set the label to either the current label or -100, depending on
            # the label_all_tokens flag.
            else:
                label_ids.append(label[word_idx] if label_all_tokens else -100)
            previous_word_idx = word_idx

        labels.append(label_ids)

    tokenized_inputs["labels"] = labels
    return tokenized_inputs

tokenize_and_align_labels(datasets['train'][:5])

tokenized_datasets = datasets.map(tokenize_and_align_labels, batched=True)

"""## Ajustando o modelo"""

from transformers import TrainingArguments, AutoModelForTokenClassification, Trainer

model = AutoModelForTokenClassification.from_pretrained(
    model_checkpoint,
    num_labels=len(label_list),
    hidden_dropout_prob=0.1,
    attention_probs_dropout_prob=0.1,
)

# biblioteca já instalada anteriormente
#pip install transformers[torch]

# biblioteca já instalada anteriormente
#!pip install accelerate==0.20.1

model_name = model_checkpoint.split("/")[-1]

# hyperparameters, which are passed into the training job

per_device_batch_size = 8
gradient_accumulation_steps = 4

#LR, wd, epochs
learning_rate = 2e-5 #2e-5 # (AdamW) we started with 3e-4, then 1e-4, then 5e-5 but the model overfits fastly
num_train_epochs = 10 # we started with 10 epochs but the model overfits fastly
weight_decay = 0.01
fp16 = True

# logs
logging_steps = 290 # melhor evaluate frequently (5000 seems too high)
logging_strategy = 'steps'
eval_steps = logging_steps

# checkpoints
evaluation_strategy = 'epoch' #steps
save_total_limit = 1 #3
save_strategy = 'epoch' #steps
save_steps = 978  #290

# best Model
load_best_model_at_end = True

# folders
model_name = model_checkpoint.split("/")[-1]
folder_model = 'e' + str(num_train_epochs) + '_lr' + str(learning_rate)

#comentado por conta do armazenamento do google drive
output_dir = '/content/drive/MyDrive/' + 'ner-lenerbr-' + str(model_name) + '/checkpoints/' + folder_model
logging_dir = '/content/drive/MyDrive/' + 'ner-lenerbr-' + str(model_name) + '/logs/' + folder_model


# get best model through a metric
metric_for_best_model = 'eval_f1'
if metric_for_best_model == 'eval_f1':
    greater_is_better = True
elif metric_for_best_model == 'eval_loss':
    greater_is_better = False

args = TrainingArguments(
    output_dir=output_dir,
    learning_rate=learning_rate,
    per_device_train_batch_size=per_device_batch_size,
    per_device_eval_batch_size=per_device_batch_size*2,
    gradient_accumulation_steps=gradient_accumulation_steps,
    num_train_epochs=num_train_epochs,
    #weight_decay=weight_decay,
    save_total_limit=save_total_limit,
    logging_steps = logging_steps,
    eval_steps = logging_steps,
    load_best_model_at_end = load_best_model_at_end,
    metric_for_best_model = metric_for_best_model,
    greater_is_better = greater_is_better,
    gradient_checkpointing = False,
    do_train = True,
    do_eval = True,
    do_predict = True,
    eval_strategy="epoch",
    save_strategy="epoch",
    logging_strategy = logging_strategy,
    logging_dir=logging_dir,
    save_steps = save_steps,
    fp16 = fp16,
    push_to_hub=False,
    max_grad_norm=1.0,  # Add this line
    warmup_steps=500,  # Add warmup steps
    weight_decay=0.01,  # Ensure proper regularization
    fp16_full_eval=False,  # Disable mixed precision during evaluation
    dataloader_num_workers=2,  # Add multiple workers
    seed=42,  # Set random seed for reproducibility
)

#!pip install transformers==4.28.0

from transformers import DataCollatorForTokenClassification

data_collator = DataCollatorForTokenClassification(tokenizer)

import evaluate
metric = evaluate.load("seqeval")

labels = [label_list[i] for i in example[f"{task}_tags"]]
metric.compute(predictions=[labels], references=[labels])

import numpy as np

def compute_metrics(p):
    predictions, labels = p
    predictions = np.argmax(predictions, axis=2)

    # Remove ignored index (special tokens) and convert to labels
    true_predictions = []
    true_labels = []

    for prediction, label in zip(predictions, labels):
        pred_list = []
        label_list_current = []

        for p, l in zip(prediction, label):
            if l != -100:  # Ignore special tokens
                try:
                    pred_list.append(label_list[p])
                    label_list_current.append(label_list[l])
                except IndexError:
                    continue  # Skip invalid indices

        if pred_list and label_list_current:  # Only add if not empty
            true_predictions.append(pred_list)
            true_labels.append(label_list_current)

    # Handle empty case
    if not true_predictions or not true_labels:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "accuracy": 0.0,
        }

    try:
        results = metric.compute(predictions=true_predictions, references=true_labels)
        return {
            "precision": float(results.get("overall_precision", 0.0) or 0.0),
            "recall": float(results.get("overall_recall", 0.0) or 0.0),
            "f1": float(results.get("overall_f1", 0.0) or 0.0),
            "accuracy": float(results.get("overall_accuracy", 0.0) or 0.0),
        }
    except Exception as e:
        print(f"Error computing metrics: {str(e)}")
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "accuracy": 0.0,
        }

from transformers.trainer_callback import EarlyStoppingCallback

# espere early_stopping_patience x eval_steps antes de interromper o treinamento para obter um modelo melhor
early_stopping_patience = 5 #save_total_limit

trainer = Trainer(
    model,
    args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["validation"],
    data_collator=data_collator,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=early_stopping_patience, early_stopping_threshold=0.01)]
)

trainer.train()

trainer.evaluate()

predictions, labels, _ = trainer.predict(tokenized_datasets["validation"])
predictions = np.argmax(predictions, axis=2)

# Remove ignored index (special tokens)
true_predictions = [
    [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
    for prediction, label in zip(predictions, labels)
]
true_labels = [
    [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
    for prediction, label in zip(predictions, labels)
]

results = metric.compute(predictions=true_predictions, references=true_labels)
results

"""#Test"""

predictions, labels, _ = trainer.predict(tokenized_datasets["test"])
predictions = np.argmax(predictions, axis=2)

# Remove ignored index (special tokens)
true_predictions = [
    [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
    for prediction, label in zip(predictions, labels)
]
true_labels = [
    [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
    for prediction, label in zip(predictions, labels)
]

results_test = metric.compute(predictions=true_predictions, references=true_labels)
results_test

"""# salvando modelo"""

model_dir = '/content/drive/MyDrive/' + 'ner-lenerbr-' + str(model_name) + '/model/'
trainer.save_model(model_dir)

"""# FIM"""