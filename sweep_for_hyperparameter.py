import wandb, config
import pandas as pd

sweep_config = {
    "name" : "my-sweep",
    'method' : 'random'
}

metric = {
    'name': 'val_f1',
    'goal': 'maximize'   
    }

sweep_config['metric'] = metric

parameters_dict = {
    'learning_rate': {
        "min" : 1e-5,
        "max" : 4e-5
        },
    'batch': {
          'values': [4, 6, 8, 12]
        },
    'epochs' : {
        'values' : [6, 7, 8, 9, 10]
    },
    'data_augmented_set' : {
        "min" : 30000,
        "max" : 75000
    },
    'word_change' : {
        'values' : [5, 6, 7, 8, 9, 10]
    }
}

sweep_config['parameters'] = parameters_dict

!wandb login --relogin
wandb.login()

sweep_id = wandb.sweep(sweep_config, project = "Pytorch_tune")

import numpy as np
from sklearn.metrics import f1_score
import torch
torch.cuda.is_available()

def f1_score_func(preds, labels):
    preds_flat = np.argmax(preds, axis=1).flatten()
    labels_flat = labels.flatten()
    return f1_score(labels_flat, preds_flat, average = 'weighted')

def evaluate(dataloader_val):
    model.eval()
    loss_val_total = 0
    predictions, true_vals = [], []
    
    for batch in tqdm(dataloader_val):
        
        batch = tuple(b.to(device) for b in batch)
        
        inputs = {'input_ids':      batch[0],
                  'attention_mask': batch[1],
                  'labels':         batch[2],
                 }

        with torch.no_grad():        
            outputs = model(**inputs)
            
        loss = outputs[0]
        logits = outputs[1]
        loss_val_total += loss.item()

        logits = logits.detach().cpu().numpy()
        label_ids = inputs['labels'].cpu().numpy()
        predictions.append(logits)
        true_vals.append(label_ids)
    
    loss_val_avg = loss_val_total/len(dataloader_val) 
    
    predictions = np.concatenate(predictions, axis=0)
    true_vals = np.concatenate(true_vals, axis=0)
            
    return loss_val_avg, predictions, true_vals

def accuracy_per_class(preds, labels):
    label_dict_inverse = {v: k for k, v in label_dict.items()}
    
    preds_flat = np.argmax(preds, axis=1).flatten()
    labels_flat = labels.flatten()
    
    for label in np.unique(labels_flat):
        y_preds = preds_flat[labels_flat==label]
        y_true = labels_flat[labels_flat==label]
        print(f'Class: {label_dict_inverse[label]}')
        print(f'Accuracy:{len(y_preds[y_preds==label])}/{len(y_true)}\n')

from tqdm.notebook import tqdm
import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from keras_preprocessing.sequence import pad_sequences
import datetime
import os
from sklearn.model_selection import train_test_split
import nlpaug
import nlpaug.augmenter.word as naw
import nltk
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from transformers import BertTokenizer, BertForPreTraining
import random
from transformers import AdamW, get_linear_schedule_with_warmup
from tqdm import tqdm  # for our progress bar
from scipy import stats
from transformers import BertForSequenceClassification
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler
from sklearn.metrics import f1_score

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')

df = pd.read_csv('/content/drive/MyDrive/Colab Notebooks/Text_Data.csv') #names = ['body', 'Sentiment']   
for i in df.index:
    df.at[i, 'Text'] = str(df.at[i, 'Text'])

df.Sentiment.value_counts()

df = df[df.Sentiment.isin(['Negative','Neutral','Positive'])]
df.Sentiment.value_counts()

possible_labels = df.Sentiment.unique()
label_dict = {}
for index, possible_label in enumerate(possible_labels):
    label_dict[possible_label] = index

df.Sentiment = df['Sentiment'].map(label_dict)

X_train, X_val, y_train, y_val = train_test_split(df.index.values, 
                                                  df.Sentiment.values, 
                                                  test_size=0.2, 
                                                  random_state=42,
                                                  stratify=df.Sentiment.values)

df['data_type'] = ['not_set']*df.shape[0]
df.loc[X_train, 'data_type'] = 'train'
df.loc[X_val, 'data_type'] = 'val'
df.groupby(['Sentiment', 'data_type']).count()

dict = {
    "clean_comment" : df[df.data_type == 'train'].Text.values,
    "category" : df[df.data_type == 'train'].Sentiment.values
}

training_data = pd.DataFrame(dict)

def DataAugmentation(training_data):
  aug = naw.SynonymAug(aug_src='wordnet',aug_max = wandb.config.word_change)
  for i in training_data.index:
    if str(training_data.at[i, 'category']) == "1":
        string = aug.augment(str(training_data.at[i, 'clean_comment']),n= int(wandb.config.data_augmented_set/(3*2050)))
        dict = {
            "clean_comment" : string,
            "category" : [training_data.at[i, 'category']]*int(wandb.config.data_augmented_set/(3*2050))
        }
        data = pd.DataFrame(dict)
        training_data = training_data.append(data)
        training_data = training_data.reset_index()
        training_data = training_data.drop(columns = ['index'])
    elif str(training_data.at[i, 'category']) == "0":
        string = aug.augment(str(training_data.at[i, 'clean_comment']),n=int(wandb.config.data_augmented_set/(3*763)))
        dict = {
            "clean_comment" : string,
            "category" : [training_data.at[i, 'category']]*int(wandb.config.data_augmented_set/(3*763))
        }
        data = pd.DataFrame(dict)
        training_data = training_data.append(data)
        training_data = training_data.reset_index()
        training_data = training_data.drop(columns = ['index'])
    elif str(training_data.at[i, 'category']) == "2":
        string = aug.augment(str(training_data.at[i, 'clean_comment']),n=int(wandb.config.data_augmented_set/(3*635)))
        dict = {
            "clean_comment" : string,
            "category" : [training_data.at[i, 'category']]*int(wandb.config.data_augmented_set/(3*635))
        }
        data = pd.DataFrame(dict)
        training_data = training_data.append(data)
        training_data = training_data.reset_index()
        training_data = training_data.drop(columns = ['index'])
  return training_data

# START: Creating Pre-Trained data
dl = pd.read_csv('/content/drive/MyDrive/Colab Notebooks/Text_Data.csv')
for i in dl.index:
    dl.at[i, 'Text'] = str(dl.at[i, 'Text'])

possible_labels = dl.Sentiment.unique()
label_dict = {'Neutral': 0, 'Positive': 1, 'Negative': 2}
  
dl.Sentiment = dl['Sentiment'].map(label_dict)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertForPreTraining.from_pretrained('bert-base-uncased')
model.to(device)

bag = [item for sentence in dl.Text for item in sentence.split('.') if item != '']
bag_size = len(bag)

sentence_a = []
sentence_b = []
label = []

for paragraph in dl.Text:
    sentences = [
        sentence for sentence in paragraph.split('.') if sentence != ''
    ]
    num_sentences = len(sentences)
    if num_sentences > 1:
        start = random.randint(0, num_sentences-2)
        # 50/50 whether is IsNextSentence or NotNextSentence
        if random.random() >= 0.5:
            # this is IsNextSentence
            sentence_a.append(sentences[start])
            sentence_b.append(sentences[start+1])
            label.append(0)
        else:
            index = random.randint(0, bag_size-1)
            # this is NotNextSentence
            sentence_a.append(sentences[start])
            sentence_b.append(bag[index])
            label.append(1)

inputs = tokenizer(sentence_a, sentence_b, return_tensors='pt',
                   max_length=512, truncation=True, padding='max_length')

inputs['next_sentence_label'] = torch.LongTensor([label]).T
inputs['labels'] = inputs.input_ids.detach().clone()

# create random array of floats with equal dimensions to input_ids tensor
rand = torch.rand(inputs.input_ids.shape)
# create mask array
mask_arr = (rand < 0.15) * (inputs.input_ids != 101) * \
           (inputs.input_ids != 102) * (inputs.input_ids != 0)

selection = []

for i in range(inputs.input_ids.shape[0]):
    selection.append(
        torch.flatten(mask_arr[i].nonzero()).tolist()
    )
    
for i in range(inputs.input_ids.shape[0]):
    inputs.input_ids[i, selection[i]] = 103

class OurDataset(torch.utils.data.Dataset):
    def __init__(self, encodings):
        self.encodings = encodings
    def __getitem__(self, idx):
        return {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
    def __len__(self):
        return len(self.encodings.input_ids)
    
dataset = OurDataset(inputs)
loader = torch.utils.data.DataLoader(dataset, batch_size=16, shuffle=True)

optim = AdamW(model.parameters(),
                  lr = 2e-5, # 학습률
                  eps = 1e-8 # 0으로 나누는 것을 방지하기 위한 epsilon 값
                )

epochs = 4

for epoch in range(epochs):
    # setup loop with TQDM and dataloader
    loop = tqdm(loader, leave=True)
    for batch in loop:
        # initialize calculated gradients (from prev step)
        optim.zero_grad()
        # pull all tensor batches required for training
        input_ids = batch['input_ids'].to(device)
        token_type_ids = batch['token_type_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        next_sentence_label = batch['next_sentence_label'].to(device)
        labels = batch['labels'].to(device)
        # process
        outputs = model(input_ids, attention_mask=attention_mask,
                        token_type_ids=token_type_ids,
                        next_sentence_label=next_sentence_label,
                        labels=labels)
        # extract loss
        loss = outputs.loss
        # calculate loss for every parameter that needs grad update
        loss.backward()
        # update parameters
        optim.step()
        # print relevant info to progress bar
        loop.set_description(f'Epoch {epoch}')
        loop.set_postfix(loss=loss.item())

model.save_pretrained("path/to/Seho-based-uncased")

from torch.utils.data import TensorDataset

tokenizer = BertTokenizer.from_pretrained(
    'bert-base-uncased',
    do_lower_case=True
  )

def input_to_data(training_data, bert_tokenize):
  tokenized_texts = bert_tokenize(training_data.clean_comment)
  input_ids_train = [tokenizer.convert_tokens_to_ids(tokens) for tokens in tokenized_texts]
  number_of_tokens = np.array([len(bert_id) for bert_id in input_ids_train])
  stats.describe(number_of_tokens)
  MAX_LEN = 512
  padded_bert_ids = pad_sequences(input_ids_train, maxlen=MAX_LEN, dtype='long',
                                        truncating='post', padding='post')

  attention_masks = []
  for seq in padded_bert_ids:
    seq_mask = [float(i>0) for i in seq]
    attention_masks.append(seq_mask)

  train_inputs = torch.tensor(padded_bert_ids)
  train_labels = torch.tensor(training_data.category.values)
  train_masks = torch.tensor(attention_masks)

  tokenized_val = bert_tokenize(df[df.data_type=='val'].Text.values)
  input_ids_val = [tokenizer.convert_tokens_to_ids(tokens) for tokens in tokenized_val]
  padded_val_ids = pad_sequences(input_ids_val, maxlen=MAX_LEN, dtype='long',
                                        truncating='post', padding='post')
  attention_masks_val = []
  for seq in padded_val_ids:
    seq_mask = [float(i>0) for i in seq]
    attention_masks_val.append(seq_mask)

  val_inputs = torch.tensor(padded_val_ids)
  val_labels = torch.tensor(df[df.data_type=='val'].Sentiment.values)
  val_masks = torch.tensor(attention_masks_val)
  dataset_train = TensorDataset(train_inputs, 
                              train_masks,
                              train_labels)

  dataset_val = TensorDataset(val_inputs, 
                              val_masks,
                            val_labels)
  
  batch_size = wandb.config.batch

  dataloader_train = DataLoader(
      dataset_train,
      sampler=RandomSampler(dataset_train),
      batch_size=batch_size
  )

  dataloader_val = DataLoader(
      dataset_val,
      sampler=RandomSampler(dataset_val),
      batch_size=32
  )

  return dataloader_train, dataloader_val

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = BertForSequenceClassification.from_pretrained(
                                      'path/to/Seho-based-uncased', 
                                      num_labels = len(label_dict),
                                      output_attentions = False,
                                      output_hidden_states = False
                                     )

from transformers import AdamW, get_linear_schedule_with_warmup

def training(training_data = training_data, model = model, device = device, tokenizer = tokenizer):
  wandb.init(config=sweep_config)

  def bert_tokenize(texts):
    return [tokenizer.tokenize("[CLS] " + text + " [SEP]") for text in texts]

  training_data = DataAugmentation(training_data)
  dataloader_train, dataloader_val = input_to_data(training_data, bert_tokenize)

  optimizer = AdamW(
    model.parameters(),
    lr = wandb.config.learning_rate, #originally 1e-5, 
    eps = 1e-8
  )

  epochs = wandb.config.epochs

  scheduler = get_linear_schedule_with_warmup(
    optimizer,
    num_warmup_steps=0,
    num_training_steps = len(dataloader_train)*epochs
  )

  model.to(device)

  seed_val = 42
  random.seed(seed_val)
  np.random.seed(seed_val)
  torch.manual_seed(seed_val)
  torch.cuda.manual_seed_all(seed_val)

  for epoch in tqdm(range(1, epochs+1)):
    
    model.train()
    loss_train_total = 0
    
    progress_bar = tqdm(dataloader_train, 
                        desc='Epoch {:1d}'.format(epoch), 
                        leave=False, 
                        disable=False)
    
    for batch in progress_bar:
        model.zero_grad()
        batch = tuple(b.to(device) for b in batch)
        inputs = {
            'input_ids': batch[0],
            'attention_mask': batch[1],
            'labels': batch[2]
        }
        
        outputs = model(**inputs)
        loss = outputs[0]
        loss_train_total +=loss.item()
        loss.backward()
        
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        
        optimizer.step()
        scheduler.step()
        
        progress_bar.set_postfix({'training_loss': '{:.3f}'.format(loss.item()/len(batch))})     
    
    #torch.save(model.state_dict(), f'Models/BERT_ft_Epoch{epoch}.model')
    
    tqdm.write('\nEpoch {epoch}')
    
    loss_train_avg = loss_train_total/len(dataloader_train)
    tqdm.write(f'Training loss: {loss_train_avg}')
    
    val_loss, predictions, true_vals = evaluate(dataloader_val)
    val_f1 = f1_score_func(predictions, true_vals)
    tqdm.write(f'Validation loss: {val_loss}')
    tqdm.write(f'F1 Score (weighted): {val_f1}')
    wandb.log({"val_f1": val_f1, "epoch": epoch})
  torch.cuda.empty_cache()

wandb.agent(sweep_id, function=training)
