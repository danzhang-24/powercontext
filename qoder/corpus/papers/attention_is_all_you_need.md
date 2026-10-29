---
title: Attention Is All You Need
authors: Ashish Vaswani, Noam Shazeer
year: 2020
venue: NeurIPS
tags: transformer, attention, nlp, sequence
kind: paper
---

# Abstract

The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.

# 一、自注意力机制

自注意力把序列中每个位置表示为对所有位置加权和。给定输入矩阵 $Q \in \mathbb{R}^{n \times d_k}$、$K \in \mathbb{R}^{n \times d_k}$、$V \in \mathbb{R}^{n \times d_v}$，注意力计算为

$$\mathrm{Attention}(Q, K, V) = \mathrm{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right) V$$

缩放因子 $\sqrt{d_k}$ 用来避免维度变大时 softmax 进入饱和区���，梯度消失。多头注意力把表示切分成多份分别做注意力再拼接，使模型能在不同子空间里关注不同关系。

# 二、位置编码

由于自注意力本身不含位置信息，模型必须显式注入顺序。论文采用正弦位置编码

$$PE_{(pos, 2i)} = \sin\left(pos / 10000^{2i/d_{model}}\right)$$

它既能表示绝对位置，也便于模型推断相对位置关系，并且可以外推到比训练时更长的序列。

# 三、多头注意力的并行计算

多头注意力的投影矩阵可以合并成一次大矩阵乘法实现，从而充分利用矩阵乘法的并行性。实践中注意力矩阵的显存占用是主要瓶颈，因此实现时通常使用 FlashAttention 一类的核融合算子把中间结果留在片上缓存。

# 四、编码器与解码器

编码器由多头自注意力、前馈网络、残差连接与层归一化堆叠六层组成；解码器额外引入交叉注意力，堆叠六层。残差连接放在层归一化之前，子层输出先残差相加再做归一化。

# 五、复杂度分析

自注意力的时间复杂度为 $O(n^2 d)$，序列长度 $n$ 增大时平方项成为主要开销。这是长序列建模的主要瓶颈，也是后续稀疏注意力、线性注意力与状态空间模型试图解决的问题。

# 六、结论

Transformer 用纯粹的注意力机制取代循环结构，在翻译任务上取得更好的效果，同时具备更高的并行度，成为后续大量模型的基础结构。
