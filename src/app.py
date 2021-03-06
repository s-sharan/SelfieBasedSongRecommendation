from flask import Flask, render_template, request, redirect, url_for
import json
import boto3
import random
import base64
from PIL import Image
import os
from loadModel import loadModel
import numpy
from boto3.dynamodb.conditions import Key,Attr
import theano
import theano.tensor as T
from theano.tensor.signal import downsample

from hw3_nn import LogisticRegression, HiddenLayer, myMLP, LeNetConvPoolLayer, train_nn
from dataLoad import loadData, shared_dataset
import cPickle
import matplotlib.pyplot as plt

app = Flask(__name__)
learning_rate=0.1 
n_epochs=1000 
nkerns=[16, 512, 20]
batch_size=200
verbose=True
rng = numpy.random.RandomState(23455)
datasets = loadData(shared=False)

validSets = datasets[1]
valid_set_x, valid_set_y = validSets
backupValidX = numpy.copy(valid_set_x)
valid_set_x, valid_set_y = shared_dataset([valid_set_x, valid_set_y])
index = T.lscalar()  # index to a [mini]batch

x = T.matrix('x')   # the data is presented as rasterized images
y = T.ivector('y')  # the labels are presented as 1D vector of
                    # [int] labels

######################
# BUILD ACTUAL MODEL #
######################
#Make learning rate a theano shared variable 

# Reshape matrix of rasterized images of shape (batch_size, 1 * 48 * 48)
# to a 4D tensor, compatible with our LeNetConvPoolLayer
layer0_input = x.reshape((batch_size, 1, 48, 48))

# TODO: Construct the first convolutional pooling layer:
layer0 = LeNetConvPoolLayer(
    rng,
    input=layer0_input,
    image_shape= (batch_size, 1, 48, 48),
    filter_shape= (nkerns[0],1,3,3),
    poolsize= (2,2)
)

# TODO: Construct the second convolutional pooling layer
layer1 = LeNetConvPoolLayer(
    rng,
    input=layer0.output,
    image_shape= (batch_size, nkerns[0], 23, 23) ,
    filter_shape= (nkerns[1],nkerns[0],4,4),
    poolsize= (2,2)
)

# TODO: Construct the third convolutional pooling layer
layer2 = LeNetConvPoolLayer(
    rng,
    input=layer1.output,
    image_shape= (batch_size,nkerns[1],10,10),
    filter_shape= (nkerns[2],nkerns[1],3,3),
    poolsize= (2,2)
)

# the HiddenLayer being fully-connected, it operates on 2D matrices of
# shape (batch_size, num_pixels) (i.e matrix of rasterized images).
# This will generate a matrix of shape (batch_size, nkerns[2] * 1 * 1).
layer3_input = layer2.output.flatten(2)

# construct a fully-connected sigmoidal layer
layer3 = HiddenLayer(
    rng,
    input=layer3_input,
    n_in=nkerns[2] * 4 * 4,
    n_out= batch_size,
    activation=T.tanh
)

# classify the values of the fully-connected sigmoidal layer
layer4 = LogisticRegression(input=layer3.output,
    n_in= batch_size,
    n_out=7)


getPofYGivenX = theano.function(
    [index],
    layer4.pOfYGivenX(),
    givens={
        x: valid_set_x[index * batch_size: (index + 1) * batch_size],
        y: valid_set_y[index * batch_size: (index + 1) * batch_size]
    },
    on_unused_input='ignore'
)

#Load the saved parameters
f = open('layer0.W','rb')
layer0.W.set_value(cPickle.load(f))
f.close()

f = open('layer0.b','rb')
layer0.b.set_value(cPickle.load(f))     
f.close()

f = open('layer1.W','rb')
layer1.W.set_value(cPickle.load(f))     
f.close()

f = open('layer1.b','rb')
layer1.b.set_value(cPickle.load(f)) 
f.close()

f = open('layer2.W','rb')
layer2.W.set_value(cPickle.load(f)) 
f.close()

f = open('layer2.b','rb')
layer2.b.set_value(cPickle.load(f))
f.close()

f = open('layer3.W','rb')
layer3.W.set_value(cPickle.load(f))
f.close()

f = open('layer3.b','rb')
layer3.b.set_value(cPickle.load(f))
f.close()

f = open('layer4.W','rb')
layer4.W.set_value(cPickle.load(f))
f.close()

f = open('layer4.b','rb')
layer4.b.set_value(cPickle.load(f))
f.close()


@app.route('/')
def index():
	return render_template('index.html')

@app.route("/pic",methods=['POST'])
def picture():
    modes = ['Angry','Disgust','Fear','Happy','Sad','Surprise','Neutral', 'Neutral']
    modeId = 7
    if(request.method== 'POST'):
        content = request.get_json()["data"]
    	data = content.split(',')[1].decode("base64")
    	file1=open('pic.png','wb')
    	file1.write(data)
    	file1.close()
    	img = Image.open('pic.png').convert('L')
    	numpyArray = numpy.array(img)
    	backupValidX[0] = numpyArray.flatten()
    	valid_set_x.set_value(backupValidX)
    	predictedList = getPofYGivenX(0)
    	predictedMoods = predictedList[0].tolist()
    	returnList = [predictedMoods.index(max(predictedMoods)),max(predictedMoods)]
        os.remove('pic.png')
        mood = modes[returnList[0]]
	print ("Mood = " + str(mood))
	dynamodb = boto3.resource('dynamodb')
	table = dynamodb.Table('songs')
	response = table.scan(
    	FilterExpression=Attr('type').eq(mood)
	)
	item = response['Items']
	num= random.randrange(0,len(item))
	res={}
	res['mood']=mood
	res['url']=item[num]['url']
	res['song']=item[num]['song']
	res['artist']=item[num]['artist']
        return str(json.dumps(res))

if __name__ == "__main__":
    app.run()
