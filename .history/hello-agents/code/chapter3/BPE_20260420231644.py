import re, collections

def get_stats(vocab):
    """统计词元对频率"""
    pairs = collections.defaultdict(int)
    for word, freq in vocab.items():
        symbols = word.split()
        for i in range(len(symbols)-1):
            pairs[symbols[i],symbols[i+1]] += freq
    return pairs

def merge_vocab(pair, v_in):
    """合并词元对"""
    v_out = {}  # 初始化一个空的输出词表
    bigram = re.escape(' '.join(pair))  # 将词元对转换成正则表达式（转义空格）
    p = re.compile(r'(?<!\S)' + bigram + r'(?!\S)')  # 创建正则表达式模式
    
    for word in v_in:  # 遍历词表中的每个词
        w_out = p.sub(''.join(pair), word)  # 将每个词中的词元对用新词元替换
        v_out[w_out] = v_in[word]  # 更新新词表
    return v_out

# 准备语料库，每个词末尾加上</w>表示结束，并切分好字符
vocab = {'h u g </w>': 1, 'p u g </w>': 1, 'p u n </w>': 1, 'b u n </w>': 1}
num_merges = 4 # 设置合并次数

for i in range(num_merges):
    pairs = get_stats(vocab)
    if not pairs:
        break
    best = max(pairs, key=pairs.get)
    vocab = merge_vocab(best, vocab)
    print(f"第{i+1}次合并: {best} -> {''.join(best)}")
    print(f"新词表（部分）: {list(vocab.keys())}")
    print("-" * 20)
