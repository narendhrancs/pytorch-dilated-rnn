import time
import argparse

import numpy as np

import torch
from torch import nn
import torch.optim as optim

from drnn import DRNN
from copy_memory.utils import data_generator
from copy_memory.model import DRNN_Copy


parser = argparse.ArgumentParser(description='Sequence Modeling - Copying Memory Task')
parser.add_argument('--batch_size', type=int, default=32, metavar='N',
                    help='batch size (default: 32)')
parser.add_argument('--cuda', action='store_false',
                    help='use CUDA (default: True)')
parser.add_argument('--dropout', type=float, default=0.0,
                    help='dropout applied to layers (default: 0.0)')
parser.add_argument('--clip', type=float, default=1.0,
                    help='gradient clip, -1 means no clip (default: 1.0)')
parser.add_argument('--epochs', type=int, default=50,
                    help='upper epoch limit (default: 50)')
parser.add_argument('--iters', type=int, default=100,
                    help='number of iters per epoch (default: 100)')
parser.add_argument('--levels', type=int, default=8,
                    help='# of levels (default: 8)')
parser.add_argument('--blank_len', type=int, default=1000, metavar='N',
                    help='The size of the blank (i.e. T) (default: 1000)')
parser.add_argument('--seq_len', type=int, default=10,
                    help='initial history size (default: 10)')
parser.add_argument('--log-interval', type=int, default=50, metavar='N',
                    help='report interval (default: 50')
parser.add_argument('--lr', type=float, default=5e-4,
                    help='initial learning rate (default: 5e-4)')
parser.add_argument('--optim', type=str, default='RMSprop',
                    help='optimizer to use (default: RMSprop)')
parser.add_argument('--nhid', type=int, default=10,
                    help='number of hidden units per layer (default: 10)')
parser.add_argument('--seed', type=int, default=1111,
                    help='random seed (default: 1111)')
args = parser.parse_args()

torch.manual_seed(args.seed)
if torch.cuda.is_available():
    if not args.cuda:
        print("WARNING: You have a CUDA device, so you should probably run with --cuda")


batch_size = args.batch_size
seq_len = args.seq_len
epochs = args.epochs
iters = args.iters
T = args.blank_len
n_steps = T + (2 * seq_len)
n_classes = 10  # Digits 0 - 9
n_train = 10000
n_test = 1000
dropout = args.dropout
input_size = 1
hidden_size = args.nhid
num_layers = args.levels


print(args)
print("Preparing data...")
train_x, train_y = data_generator(T, seq_len, n_train)
test_x, test_y = data_generator(T, seq_len, n_test)


model = DRNN_Copy(input_size=input_size,
                  hidden_size=hidden_size,
                  num_layers=num_layers,
                  dropout=dropout,
                  output_size=n_classes)


if torch.cuda.is_available():
    model.cuda()
    train_x = train_x.cuda()
    train_y = train_y.cuda()
    test_x = test_x.cuda()
    test_y = test_y.cuda()

criterion = nn.CrossEntropyLoss()
lr = args.lr
optimizer = optim.RMSprop(model.parameters(), lr=lr)


def evaluate():
    model.eval()
    out =  model(test_x.unsqueeze(2).contiguous())
    loss = criterion(out.view(-1, n_classes), test_y.view(-1))
    pred = out.view(-1, n_classes).data.max(1, keepdim=True)[1]
    correct = pred.eq(test_y.data.view_as(pred)).cpu().sum()
    counter = out.view(-1, n_classes).size(0)
    print('\nTest set: Average loss: {:.8f}  |  Accuracy: {:.4f}\n'.format(
        loss.data[0], 100. * correct / counter))
    return loss.data[0]


def train(ep):
    global batch_size, seq_len, iters, epochs
    model.train()
    total_loss = 0
    start_time = time.time()
    correct = 0
    counter = 0
    for batch_idx, batch in enumerate(range(0, n_train, batch_size)):
        start_ind = batch
        end_ind = start_ind + batch_size

        x = train_x[start_ind:end_ind] # (batch, steps)
        y = train_y[start_ind:end_ind] # (batch, steps)

        #import pdb
        #pdb.set_trace()

        optimizer.zero_grad()
        out = model(x.unsqueeze(2).contiguous()) # out: (batch, steps, output_size)

        loss = criterion(out.view(-1, n_classes), y.view(-1))
        pred = out.view(-1, n_classes).data.max(1, keepdim=True)[1]
        correct += pred.eq(y.data.view_as(pred)).cpu().sum()
        counter += out.view(-1, n_classes).size(0)
        if args.clip > 0:
            torch.nn.utils.clip_grad_norm(model.parameters(), args.clip)
        loss.backward()
        optimizer.step()
        total_loss += loss

        if batch_idx > 0 and batch_idx % args.log_interval == 0:
            avg_loss = total_loss / args.log_interval
            elapsed = time.time() - start_time
            print('| Epoch {:3d} | {:5d}/{:5d} batches | lr {:2.5f} | ms/batch {:5.2f} | '
                  'loss {:5.8f} | accuracy {:5.4f}'.format(
                ep, batch_idx, n_train // batch_size+1, args.lr, elapsed * 1000 / args.log_interval,
                avg_loss.data[0], 100. * correct / counter))
            start_time = time.time()
            total_loss = 0
            correct = 0
            counter = 0


for ep in range(1, epochs + 1):
    train(ep)
    evaluate()