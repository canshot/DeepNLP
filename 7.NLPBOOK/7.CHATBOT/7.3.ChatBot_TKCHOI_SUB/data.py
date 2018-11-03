from konlpy.tag import Twitter
import pandas as pd
import tensorflow as tf
import enum
import os
import re
from sklearn.model_selection import train_test_split
import numpy as np
from configs import DEFINES

from tqdm import tqdm

FILTERS = "([~.,!?\"':;)(])"
PAD = "<PADDING>"
STD = "<START>"
END = "<END>"
UNK = "<UNKNWON>"

PAD_INDEX = 0
STD_INDEX = 1
END_INDEX = 2
UNK_INDEX = 3

MARKER = [PAD, STD, END, UNK]
changeFilter = re.compile(FILTERS)


def loadData():
    # 판다스를 통해서 데이터를 불러온다.
    dataDF = pd.read_csv(DEFINES.dataPath, header=0)
    # 질문과 답변 열을 가져와 question과 answer에 넣는다.
    question, answer = list(dataDF['Q']), list(dataDF['A'])
    # skleran에서 지원하는 함수를 통해서 학습 셋과 
    # 테스트 셋을 나눈다.
    xTrain, xTest, yTrain, yTest = train_test_split(question, answer, test_size=0.33, random_state=42)
    # 그 값을 리턴한다.
    return xTrain, yTrain, xTest, yTest


def preproLikeMorphlized(data):
    # 형태소 분석 모듈 객체를
    # 생성합니다.
    print("Preprocessed by morph tokenizer...")
    morphAnalyzer = Twitter()
    # 형태소 토크나이즈 결과 문장을 받을
    #  리스트를 생성합니다.
    result_data = list()
    # 데이터에 있는 매 문장에 대해 토크나이즈를
    # 할 수 있도록 반복문을 선언합니다.
    for seq in tqdm(data):
        # Twitter.morphs 함수를 통해 토크나이즈 된
        # 리스트 객체를 받고 다시 공백문자를 기준으로
        # 하여 문자열로 재구성 해줍니다.
        morphlizedSeq = " ".join(morphAnalyzer.morphs(seq.replace(' ', '')))
        result_data.append(morphlizedSeq)

    return result_data


# 인덱스화 할 xValue와 키가 워드이고 
# 값이 인덱스인 딕셔너리를 받는다.
def encProcessing(xValue, dictionary):
    # 인덱스 값들을 가지고 있는 
    # 배열이다.(누적된다.)
    sequencesInputIndex = []
    # 하나의 인코딩 되는 문장의 
    # 길이를 가지고 있다.(누적된다.)
    sequencesLength = []
    # 형태소 토크나이징 사용 유무
    if DEFINES.tokenizeAsMorph:
        xValue = preproLikeMorphlized(xValue)

    # 한줄씩 불어온다.
    for sequence in xValue:
        # FILTERS = "([~.,!?\"':;)(])"
        # 정규화를 사용하여 필터에 들어 있는 
        # 값들을 "" 으로 치환 한다.
        sequence = re.sub(changeFilter, "", sequence)
        # 하나의 문장을 인코딩 할때 
        # 가지고 있기 위한 배열이다.
        sequenceIndex = []
        # 문장을 스페이스 단위로 
        # 자르고 있다.
        for word in sequence.split():
            # 잘려진 단어들이 딕셔너리에 존재 하는지 보고 
            # 그 값을 가져와 sequenceIndex에 추가한다.
            if dictionary.get(word) is not None:
                sequenceIndex.extend([dictionary[word]])
            # 잘려진 단어가 딕셔너리에 존재 하지 않는 
            # 경우 이므로 UNK(2)를 넣어 준다.
            else:
                sequenceIndex.extend([dictionary[UNK]])
        # 문장 제한 길이보다 길어질 경우 뒤에 토큰을 자르고 있다.
        if len(sequenceIndex) > DEFINES.maxSequenceLength:
            sequenceIndex = sequenceIndex[:DEFINES.maxSequenceLength]
        # 하나의 문장에 길이를 넣어주고 있다.
        sequencesLength.append(len(sequenceIndex))
        # maxSequenceLength보다 문장 길이가 
        # 작다면 빈 부분에 PAD(0)를 넣어준다.
        sequenceIndex += (DEFINES.maxSequenceLength - len(sequenceIndex)) * [dictionary[PAD]]
        # 인덱스화 되어 있는 값을 
        # sequencesInputIndex에 넣어 준다.
        sequenceIndex.reverse()
        sequencesInputIndex.append(sequenceIndex)
    # 인덱스화된 일반 배열을 넘파이 배열로 변경한다. 
    # 이유는 텐서플로우 dataset에 넣어 주기 위한 
    # 사전 작업이다.
    # 넘파이 배열에 인덱스화된 배열과 
    # 그 길이를 넘겨준다.  
    return np.asarray(sequencesInputIndex), sequencesLength


# 인덱스화 할 yValue와 키가 워드 이고
# 값이 인덱스인 딕셔너리를 받는다.
def decTargetProcessing(yValue, dictionary):
    # 인덱스 값들을 가지고 있는 
    # 배열이다.(누적된다)
    sequencesTargetIndex = []
    # 형태소 토크나이징 사용 유무
    if DEFINES.tokenizeAsMorph:
        yValue = preproLikeMorphlized(yValue)
    # 한줄씩 불어온다.
    for sequence in yValue:
        # FILTERS = "([~.,!?\"':;)(])"
        # 정규화를 사용하여 필터에 들어 있는 
        # 값들을 "" 으로 치환 한다.
        sequence = re.sub(changeFilter, "", sequence)
        # 문장에서 스페이스 단위별로 단어를 가져와서 
        # 딕셔너리의 값인 인덱스를 넣어 준다.
        # 디코딩 출력의 마지막에 END를 넣어 준다.
        sequenceIndex = [dictionary[word] for word in sequence.split()]
        # 문장 제한 길이보다 길어질 경우 뒤에 토큰을 자르고 있다.
        # 그리고 END 토큰을 넣어 준다
        if len(sequenceIndex) >= DEFINES.maxSequenceLength:
            sequenceIndex = sequenceIndex[:DEFINES.maxSequenceLength-1] + [dictionary[END]]
        else:
            sequenceIndex += [dictionary[END]]
        # maxSequenceLength보다 문장 길이가 
        # 작다면 빈 부분에 PAD(0)를 넣어준다.
        sequenceIndex += (DEFINES.maxSequenceLength - len(sequenceIndex)) * [dictionary[PAD]]
        # 인덱스화 되어 있는 값을 
        # sequencesTargetIndex에 넣어 준다.
        sequencesTargetIndex.append(sequenceIndex)
    # 인덱스화된 일반 배열을 넘파이 배열로 변경한다. 
    # 이유는 텐서플로우 dataset에 넣어 주기 위한 사전 작업이다.
    # 넘파이 배열에 인덱스화된 배열과 그 길이를 넘겨준다.
    return np.asarray(sequencesTargetIndex)


# 인덱스를 스트링으로 변경하는 함수이다.
# 바꾸고자 하는 인덱스 value와 인덱스를 
# 키로 가지고 있고 값으로 단어를 가지고 있는 
# 딕셔너리를 받는다.
def pred2string(value, dictionary):
    # 텍스트 문장을 보관할 배열을 선언한다.
    sentenceString = []
    # 인덱스 배열 하나를 꺼내서 v에 넘겨준다.
    for v in value:
        # 딕셔너리에 있는 단어로 변경해서 배열에 담는다.
        sentenceString = [dictionary[index] for index in v['indexs']]
    
    print(sentenceString)
    answer = ""
    # 패딩값도 담겨 있으므로 패딩은 모두 스페이스 처리 한다.
    for word in sentenceString:
        if word not in PAD and word not in END:
            answer += word
            answer += " "
    # 결과를 출력한다.
    print(answer)
    return answer


def rearrange(input, target):
    features = {"input": input}
    return features, target


# 학습에 들어가 배치 데이터를 만드는 함수이다.
def trainInputFn(inputTrainEnc, targetTrainDec, batchSize):
    # Dataset을 생성하는 부분으로써 from_tensor_slices부분은 
    # 각각 한 문장으로 자른다고 보면 된다.
    # inputTrainEnc, outputTrainDec, targetTrainDec 
    # 3개를 각각 한문장으로 나눈다.
    dataset = tf.data.Dataset.from_tensor_slices((inputTrainEnc, targetTrainDec))
    # 전체 데이터를 썩는다.
    dataset = dataset.shuffle(buffer_size=len(inputTrainEnc))
    # 배치 인자 값이 없다면  에러를 발생 시킨다.
    assert batchSize is not None, "train batchSize must not be None"
    # from_tensor_slices를 통해 나눈것을 
    # 배치크기 만큼 묶어 준다.
    dataset = dataset.batch(batchSize)
    # 데이터 각 요소에 대해서 rearrange 함수를 
    # 통해서 요소를 변환하여 맵으로 구성한다.
    dataset = dataset.map(rearrange)
    # repeat()함수에 원하는 에포크 수를 넣을수 있으면 
    # 아무 인자도 없다면 무한으로 이터레이터 된다.
    dataset = dataset.repeat()
    # make_one_shot_iterator를 통해 이터레이터를 
    # 만들어 준다.
    iterator = dataset.make_one_shot_iterator()
    # 이터레이터를 통해 다음 항목의 텐서 
    # 개체를 넘겨준다.
    return iterator.get_next()


# 평가에 들어가 배치 데이터를 만드는 함수이다.
def evalInputFn(inputTestEnc, targetTestDec, batchSize):
    # Dataset을 생성하는 부분으로써 from_tensor_slices부분은 
    # 각각 한 문장으로 자른다고 보면 된다.
    # inputTestEnc, outputTestDec, targetTestDec 
    # 3개를 각각 한문장으로 나눈다.
    dataset = tf.data.Dataset.from_tensor_slices((inputTestEnc, targetTestDec))
    # 전체 데이터를 섞는다.
    dataset = dataset.shuffle(buffer_size=len(inputTestEnc))
    # 배치 인자 값이 없다면  에러를 발생 시킨다.
    assert batchSize is not None, "eval batchSize must not be None"
    # from_tensor_slices를 통해 나눈것을 
    # 배치크기 만큼 묶어 준다.
    dataset = dataset.batch(batchSize)
    # 데이터 각 요소에 대해서 rearrange 함수를 
    # 통해서 요소를 변환하여 맵으로 구성한다.
    dataset = dataset.map(rearrange)
    # repeat()함수에 원하는 에포크 수를 넣을수 있으면 
    # 아무 인자도 없다면 무한으로 이터레이터 된다.
    # 평가이므로 1회만 동작 시킨다.
    dataset = dataset.repeat(1)
    # make_one_shot_iterator를 통해 
    # 이터레이터를 만들어 준다.
    iterator = dataset.make_one_shot_iterator()
    # 이터레이터를 통해 다음 항목의 
    # 텐서 개체를 넘겨준다.
    return iterator.get_next()


def dataTokenizer(data):
    # 토크나이징 해서 담을 배열 생성
    words = []
    for sentence in data:
        # FILTERS = "([~.,!?\"':;)(])"
        # 위 필터와 같은 값들을 정규화 표현식을 
        # 통해서 모두 "" 으로 변환 해주는 부분이다.
        sentence = re.sub(changeFilter, "", sentence)
        for word in sentence.split():
            words.append(word)
    # 토그나이징과 정규표현식을 통해 만들어진 
    # 값들을 넘겨 준다.
    return [word for word in words if word]


def loadVocabulary():
    # 사전을 담을 배열 준비한다.
    vocabularyList = []
    # 사전을 구성한 후 파일로 저장 진행한다. 
    # 그 파일의 존재 유무를 확인한다.
    if (not (os.path.exists(DEFINES.vocabularyPath))):
        # 이미 생성된 사전 파일이 존재하지 않으므로 
        # 데이터를 가지고 만들어야 한다.
        # 그래서 데이터가 존재 하면 사전을 만들기 위해서 
        # 데이터 파일의 존재 유무를 확인한다.
        if (os.path.exists(DEFINES.dataPath)):
            # 데이터가 존재하니 판단스를 통해서 
            # 데이터를 불러오자
            dataDF = pd.read_csv(DEFINES.dataPath, encoding='utf-8')
            # 판다스의 데이터 프레임을 통해서 
            # 질문과 답에 대한 열을 가져 온다.
            question, answer = list(dataDF['Q']), list(dataDF['A'])
            if DEFINES.tokenizeAsMorph:  # 형태소에 따른 토크나이져 처리
                question = preproLikeMorphlized(question)
                answer = preproLikeMorphlized(answer)
            data = []
            # 질문과 답변을 extend을 
            # 통해서 구조가 없는 배열로 만든다.
            data.extend(question)
            data.extend(answer)
            # 토큰나이져 처리 하는 부분이다.
            words = dataTokenizer(data)
            # 공통적인 단어에 대해서는 모두 
            # 필요 없으므로 한개로 만들어 주기 위해서
            # set해주고 이것들을 리스트로 만들어 준다.
            words = list(set(words))
            # 데이터 없는 내용중에 MARKER를 사전에 
            # 추가 하기 위해서 아래와 같이 처리 한다.
            # 아래는 MARKER 값이며 리스트의 첫번째 부터 
            # 순서대로 넣기 위해서 인덱스 0에 추가한다.
            # PAD = "<PADDING>"
            # STD = "<START>"
            # END = "<END>"
            # UNK = "<UNKNWON>"     
            words[:0] = MARKER
        # 사전을 리스트로 만들었으니 이 내용을 
        # 사전 파일을 만들어 넣는다.
        with open(DEFINES.vocabularyPath, 'w') as vocabularyFile:
            for word in words:
                vocabularyFile.write(word + '\n')

    # 사전 파일이 존재하면 여기에서 
    # 그 파일을 불러서 배열에 넣어 준다.
    with open(DEFINES.vocabularyPath, 'r', encoding='utf-8') as vocabularyFile:
        for line in vocabularyFile:
            vocabularyList.append(line.strip())

    # 배열에 내용을 키와 값이 있는 
    # 딕셔너리 구조로 만든다.
    char2idx, idx2char = makeVocabulary(vocabularyList)
    # 두가지 형태의 키와 값이 있는 형태를 리턴한다. 
    # (예) 단어: 인덱스 , 인덱스: 단어)
    return char2idx, idx2char, len(char2idx)


def makeVocabulary(vocabularyList):
    # 리스트를 키가 단어이고 값이 인덱스인 
    # 딕셔너리를 만든다.
    char2idx = {char: idx for idx, char in enumerate(vocabularyList)}
    # 리스트를 키가 인덱스이고 값이 단어인 
    # 딕셔너리를 만든다.
    idx2char = {idx: char for idx, char in enumerate(vocabularyList)}
    # 두개의 딕셔너리를 넘겨 준다.
    return char2idx, idx2char


def main(self):
    char2idx, idx2char, vocabularyLength = loadVocabulary()


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)
    tf.app.run(main)
