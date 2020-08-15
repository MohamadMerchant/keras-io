"""
Title: Semantic Similarity with BERT
Author: Mohamad Merchant
Date created: 2020/08/15
Last modified: 2020/08/15
Description: Natural Language Inference by Fine tuning BERT model on SNLI Corpus.
"""
"""
## **Introduction**

Semantic Similarity or Natural Languauge Inference is the task of determining how two
sentences are similar to each other in terms of their meaning.
This example demonstrates the use of SNLI (Standford Natural Language Inference) Corpus
to perform semantic similarity with Transformers.
We will fine-tune BERT model by providing two sentences as inputs and it outputs the
probability of the similarity between sentences.

### References
* [BERT](https://arxiv.org/pdf/1810.04805.pdf)
* [SNLI](https://nlp.stanford.edu/projects/snli/)
"""

"""
## Setup
"""

import numpy as np
import pandas as pd
import tensorflow as tf
import transformers
from transformers import BertTokenizer, TFBertModel

"""
## Configurations
"""

MAXLEN = 128
BATCH_SIZE = 32
EPOCHS = 4
LR = 3e-5
np.random.seed(42)
# we will use base-base-uncased pretrained model
MODEL = "bert-base-uncased"

"""
## Load the Data
"""

"""shell
curl -LO https://raw.githubusercontent.com/MohamadMerchant/SNLI/master/data.tar.gz
tar -xvzf data.tar.gz
"""

train_df = pd.read_csv("SNLI_Corpus/snli_1.0_train.csv")
valid_df = pd.read_csv("SNLI_Corpus/snli_1.0_dev.csv")
test_df = pd.read_csv("SNLI_Corpus/snli_1.0_test.csv")

# Shape of the data
print(f"Total train samples : {train_df.shape[0]}")
print(f"Total validation samples: {valid_df.shape[0]}")
print(f"Total test samples: {valid_df.shape[0]}")

"""
  Dataset Info:

        sentence1: The premise caption that was supplied to the author of the pair.

        sentence2: The hypothesis caption that was written by the author of the pair.

        similarity: This is the label chosen by the majority of annotators.
                    Where no majority exists, this is '-' which we will not use in our
                    task.
                    {
                          "Contradiction": "The sentences have no similarity or
                                            different from each other"
                          "Entailment":    "The sentences have similar meaning."
                          "Neutral":       "The sentences are neutral."
                    }

  Lets look at one sample of data:
"""
print(f"Sentence1: {train_df.loc[1, 'sentence1']}")
print(f"Sentence2: {train_df.loc[1, 'sentence2']}")
print(f"Similarity: {train_df.loc[1, 'similarity']}")

"""
## Preprocessing
"""

# we have some nan in our train data, we will simply drop them
print(train_df.isnull().sum())
train_df.dropna(axis=0, inplace=True)

# we have some "-" in our train and validation targets, so we will not use those.
train_df = (
    train_df[train_df.similarity != "-"]
    .sample(frac=1.0, random_state=42)
    .reset_index(drop=True)
)
valid_df = (
    valid_df[valid_df.similarity != "-"]
    .sample(frac=1.0, random_state=42)
    .reset_index(drop=True)
)

"""
Let's check distribution of our training and validation targets
"""
print(train_df.similarity.value_counts())

print(valid_df.similarity.value_counts())

"""
One hot encoding training, validation and test labels
"""
train_df["label"] = train_df["similarity"].apply(
    lambda x: 0 if x == "contradiction" else 1 if x == "entailment" else 2
)
y_train = tf.keras.utils.to_categorical(train_df.label, num_classes=3)

valid_df["label"] = valid_df["similarity"].apply(
    lambda x: 0 if x == "contradiction" else 1 if x == "entailment" else 2
)
y_val = tf.keras.utils.to_categorical(valid_df.label, num_classes=3)

test_df["label"] = test_df["similarity"].apply(
    lambda x: 0 if x == "contradiction" else 1 if x == "entailment" else 2
)
y_test = tf.keras.utils.to_categorical(test_df.label, num_classes=3)

"""
## Keras Custom Data Generator
"""


class DataGenerator(tf.keras.utils.Sequence):
    """
        Generates batch data for Keras.

        Parameters:
            sentence1: Text Input 1
            sentence2: Text Input 2
            labels: Targets
            batch_size: Size of the batch
            shuffle: Whether to shuffle data or not
            train: Use DataGenerator for train or test purpose
        Returns:
            Encoded features: input_ids, attention_mask, token_type_ids
                              and labels if train is set to true
    """

    def __init__(
        self,
        sentence1,
        sentence2,
        labels,
        batch_size=BATCH_SIZE,
        shuffle=True,
        train=True,
    ):
        self.sentence1 = sentence1
        self.sentence2 = sentence2
        self.labels = labels
        self.shuffle = shuffle
        self.batch_size = batch_size
        self.train = train
        # load our BERT Tokenizer to encode the text
        self.tokenizer = BertTokenizer.from_pretrained(MODEL, do_lower_case=True)
        self.on_epoch_end()

    def __len__(self):
        # Denotes the number of batches per epoch
        return len(self.sentence1) // self.batch_size

    def __getitem__(self, idx):
        # Generates batch of data
        indexes = self.indexes[idx * self.batch_size : (idx + 1) * self.batch_size]
        sentence1 = self.sentence1[indexes]
        sentence2 = self.sentence2[indexes]
        batch_input_ids = []
        batch_attention_masks = []
        batch_token_type_ids = []
        # encoding both the sentences together. With
        # BERT tokenizer's encode plus both the sentences are
        # encoded together and separated by [SEP] token.
        # here we are encoding batch of sentences together.
        for s1, s2 in zip(sentence1, sentence2):
            encoded = self.tokenizer.encode_plus(
                s1,
                s2,
                add_special_tokens=True,
                max_length=MAXLEN,
                return_attention_mask=True,
                return_token_type_ids=True,
                padding=True,
                pad_to_max_length=True,
                pad_to_multiple_of=MAXLEN,
                return_tensors="tf",
            )
            batch_input_ids.extend(encoded["input_ids"])
            batch_attention_masks.extend(encoded["attention_mask"])
            batch_token_type_ids.extend(encoded["token_type_ids"])

        # convert batch of encoded features to numpy arary
        input_ids = np.array(batch_input_ids, dtype="int32")
        masks = np.array(batch_attention_masks, dtype="int32")
        token_type_ids = np.array(batch_token_type_ids, dtype="int32")

        # set to true if data generator is used for training/validation
        if self.train:
            labels = np.array(self.labels[indexes], dtype="int32")
            return [input_ids, masks, token_type_ids], labels
        else:
            return [input_ids, masks, token_type_ids]

    def on_epoch_end(self):
        # shuffle indexes after each epoch if self.shuffle is set to True
        self.indexes = np.arange(len(self.sentence1))
        if self.shuffle:
            np.random.shuffle(self.indexes)


"""
## Build The Model
"""


def build_model():
    """
    model inputs:
                  input_ids:       Encoded token Ids from BERT tokenizer.
                  attention_masks: This argument indicates to the model which
                                   tokens should be attended to.
                  token_type_ids:  They are binary masks identifying different
                                   sequences in the model.
    """
    input_ids = tf.keras.layers.Input(shape=(MAXLEN,), dtype=tf.int32, name="input_ids")
    attention_masks = tf.keras.layers.Input(
        shape=(MAXLEN,), dtype=tf.int32, name="att_mask"
    )
    token_type_ids = tf.keras.layers.Input(
        shape=(MAXLEN,), dtype=tf.int32, name="tt_ids"
    )
    # Loading pretrained BERT model
    bertModel = TFBertModel.from_pretrained(MODEL)
    seq_output, pooled_output = bertModel(
        input_ids, attention_mask=attention_masks, token_type_ids=token_type_ids
    )
    # applying hybrid pooling approach to our seq output
    avg_pool = tf.keras.layers.GlobalAveragePooling1D()(seq_output)
    max_pool = tf.keras.layers.GlobalMaxPooling1D()(seq_output)
    concat = tf.keras.layers.concatenate([avg_pool, max_pool])
    dropout = tf.keras.layers.Dropout(0.1)(concat)
    output = tf.keras.layers.Dense(3, activation="softmax")(dropout)

    model = tf.keras.models.Model(
        inputs=[input_ids, attention_masks, token_type_ids], outputs=output
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(lr=LR),
        loss="categorical_crossentropy",
        metrics=["acc"],
    )
    return model


"""

"""
# Recommended training on GPU Runtime
try:
    # build model with distributed strategy
    strategy = tf.distribute.MirroredStrategy()
    with strategy.scope():
        model = build_model()
    print(f"Strategy: {strategy}")
except:
    model = build_model()

model.summary()

"""
Create train and validation data generators
"""
train_data = DataGenerator(
    train_df.sentence1.astype("str"),
    train_df.sentence2.astype("str"),
    y_train,
    batch_size=BATCH_SIZE,
    shuffle=True,
)
valid_data = DataGenerator(
    valid_df.sentence1.astype("str"),
    valid_df.sentence2.astype("str"),
    y_val,
    batch_size=BATCH_SIZE,
    shuffle=False,
)

"""
## Train the Model
"""
h = model.fit_generator(
    train_data,
    steps_per_epoch=len(train_data) // BATCH_SIZE,
    validation_data=valid_data,
    validation_steps=len(valid_data) // BATCH_SIZE,
    epochs=EPOCHS,
)

"""
## Evaluate model on test set
"""
test_data = DataGenerator(
    test_df.sentence1.astype("str"),
    test_df.sentence2.astype("str"),
    y_test,
    batch_size=BATCH_SIZE,
    shuffle=False,
)
model.evaluate_generator(test_data, steps=len(test_data) // BATCH_SIZE, verbose=1)

"""
## Inference on custom sentences
"""
LABELS = ["CONTRADICTION", "ENTAILMENT", "NEUTRAL"]


def check_similarity(sentence1, sentence2):
    sentence1 = np.array([str(sentence1)])
    sentence2 = np.array([str(sentence2)])
    test_data = DataGenerator(
        sentence1, sentence2, labels=None, shuffle=False, batch_size=1, train=False
    )

    proba = model.predict(test_data)[0]
    idx = np.argmax(proba)
    proba = f"{proba[idx]: .2f}%"
    pred = LABELS[idx]
    return pred, proba


"""

"""
sentence1 = "The man is sleeping"
sentence2 = "A man inspects the uniform"
print(check_similarity(sentence1, sentence2))

"""

"""
sentence1 = "A smiling costumed woman is holding an umbrella"
sentence2 = "A happy woman in a fairy costume holds an umbrella"
print(check_similarity(sentence1, sentence2))

"""

"""
sentence1 = "A soccer game with multiple males playing"
sentence2 = "Some men are playing a sport"
print(check_similarity(sentence1, sentence2))
