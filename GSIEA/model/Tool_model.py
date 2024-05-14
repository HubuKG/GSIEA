from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division
from __future__ import print_function

import torch
import torch.nn as nn
import torch.nn.functional as F

from .layers import MultiHeadGraphAttention,GraphConvolution

class AutomaticWeightedLoss(nn.Module):
    def __init__(self,num=2,args=None):
        super(AutomaticWeightedLoss,self).__init__()
        if args is None or args.use_awl:
            params = torch.ones(num,requires_grad=True)
            self.params = torch.nn.Parameter(params)
        else:
            params = torch.ones(num,requires_grad=False)
            self.params = torch.nn.Parameter(params,requires_grad=False)

    def forward(self,*x):
        loss_sum=0
        for i,loss in enumerate(x):
            loss_sum += 0.5 / (self.params[i] ** 2) * loss + torch.log(1 + self.params[i] ** 2)
        return loss_sum

class GAT(nn.Module):
    def __init__(self,n_units,n_heads,dropout,attn_dropout,instance_normalization,diag):
        super(GAT,self).__init__()
        self.num_layer = len(n_units) - 1
        self.dropout = dropout
        self.inst_norm = instance_normalization
        if self.inst_norm:
            self.norm = nn.InstanceNorm1d(n_units[0],momentum=0.0,affine=True)
        self.layer_stack = nn.ModuleList()
        self.diag = diag
        for i in range(self.num_layer):
            f_in = n_units[i] * n_heads[i - 1] if i else n_units[i]
            self.layer_stack.append(MultiHeadGraphAttention(n_heads[i],f_in,n_units[i+1],attn_dropout,diag,nn.init.ones_,False))

    def forward(self,x,adj):
        if self.inst_norm:
            x = self.norm(x)
        for i,get_layer in enumerate(self.layer_stack):
            if i + 1 < self.num_layer:
                x = F.dropout(x,self.dropout,training=self.training)

            x = get_layer(x, adj)

            if self.diag:
                x=x.mean(dim = 0)
            if i + 1 < self.num_layer:
                if self.diag:
                    x=F.elu(x)
                else:
                    x=F.elu(x.transpose(0,1).contiguous().view(adj.size(0),-1))
        if not self.diag:
            x=x.mean(dim=0)

        return x

class GCN(nn.Module):
    def __init__(self,nfeat,nhid,nout,dropout):
        super(GCN,self).__init__()

        self.gc1 = GraphConvolution(nfeat,nhid)
        self.gc2 = GraphConvolution(nhid,nout)
        self.dropout = dropout

    def forward(self,x,adj):
        x=F.relu(self.gc1(x,adj))
        x=F.dropout(x,self.dropout,training=self.training)
        x=self.gc2(x,adj)
        return x