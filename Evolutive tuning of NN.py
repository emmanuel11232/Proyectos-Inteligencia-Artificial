from scipy.io import arff
import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import math
import random
import multiprocessing
import re
import sklearn
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import class_weight
from scipy.stats import zscore
from keras.utils import plot_model
import array

!pip install deap
from deap import base
from deap import creator
from deap import tools
from deap import algorithms


#Se elimina la sesión anterior, esto para evitar fallos
tf.keras.backend.clear_session()

#Se lee el excel con todos los datos necesarios, en este caso
#solo se utiliza el dataset lp1 y el lp4

data = arff.loadarff('Dataset.arff')
TrainInputs = pd.DataFrame(data[0])

#=====================Preprocesado de datos==================================

#Se define la función ArrayRespuestas que cambia las clasificaciones de palabras
#a clasificaciones numéricas
def ArrayRespuestas(data):
  #Se lee el dataset y si algún dato coincide, se cambia por
  #su valor numérico
  if data == "b'1'":
      data= 0.0001
  elif data=="b'2'":
      data= 1.0
  elif data=="b'3'":
      data = 2.0
  elif data=="b'4'":
      data = 3.0
  return data


#Se cambian las clasificaciones por los valores numéricos
TrainInputs["Class"] = TrainInputs["Class"].apply(lambda x: ArrayRespuestas(x))
TrainInputs = TrainInputs.astype(float)#Se convierten los datos a float
#Se normaliza cada columna y no se normalizan las salidas
for x in TrainInputs.columns:
  if x=='Class':
    TrainInputs[x]=TrainInputs[x]
  else:
    TrainInputs[x]=zscore(TrainInputs[x])#Se utiliza la normalización mediante zscore


#Se calculan los pesos de cada clase para realizar un balanceo de clases
class_weights=sklearn.utils.class_weight.compute_class_weight("balanced",classes=np.unique(TrainInputs["Class"]),y=TrainInputs["Class"])
TrainInputs = TrainInputs.astype(float) #Se asegura de que los datos sean float

#Se crean vectores de 4 valores, hot encoded, un valor para cada clasificación
Y = TrainInputs["Class"]
encoder = LabelEncoder()
encoder.fit(Y)
encoded_Y = encoder.transform(Y)
dummy_y = tf.keras.utils.to_categorical(encoded_Y)

#Se divide en datos de entrenamiento, validación y testeo
#Se van a tener 5% de los datos para testeo
X_train, X_val, y_train, y_val = train_test_split(TrainInputs.drop('Class',axis=1), dummy_y, test_size=0.05, random_state=1)
#19% de los datos para validación y 76% para entrenamiento
X_train, X_test, y_train, y_test = train_test_split(X_train, y_train, test_size=0.2, random_state=1)

#=========================Funciones para evolutivo==================================================================================================

def mutacion(individuo,indpb):
  #Recorrido de genes de cada individuo
  for gen in range(len(individuo)):
    #Mutación con probabilidad independiente de cada gen (indpb)
    if random.random() < indpb:
      #Se reemplazan con algún otro valor de la lista de posibles diámetros
      if gen==0:
        individuo[gen]=random.randint(1,6)
      elif gen==1:
        individuo[gen]=random.randint(1,14)
      elif gen==2:
        individuo[gen]=random.uniform(0.00001,0.5)
      elif gen==3:
        individuo[gen]=random.randint(0,2)
      elif gen==4:
        individuo[gen]=not bool(individuo[gen])
  return individuo,

def RedNeuronalQual(individuo):
  # número de capas ocultas: de 1 a 6
  # número de neuronas por capa oculta: de 1 a 14
  # tasa de aprendizaje: de 0.00001 a 0.5
  # tipo de optimizador: al menos tres tipos diferentes (a plantear por ustedes)
  # uso de término de momento: binario (si o no)
  global X_train, X_val, y_train, y_val, X_test, y_test
  Capas_ocultas=int(individuo[0]) #Se definen las capas capas intermedias (2,3,4) y su cantidad de neuronas
  Neur_per_layer=int(individuo[1])
  TasaApr=individuo[2] #Tasa de aprendizaje
  Optim=int(individuo[3])
  Momento=bool(individuo[4])

  ActivationHLs="sigmoid" #Función de activación a utilizar en todas las capas ocultas
  NEpochs=100 #Cantidad de épocas para entrenamiento
  lossF="categorical_crossentropy" #Función de pérdida

  #Se definen los callbacks, estos son los responsables de las técnicas de
  #Early stopping y el guardado de pesos de la mejor época
  callbacks = [
      tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=0.2*NEpochs)
      ]
  #Se crea el modelo de red neuronal
  network = tf.keras.models.Sequential()

  #Se agrega la capa de entrada a la red con 90 entradas
  network.add(tf.keras.layers.Dense(
  units=Neur_per_layer,
  input_shape=[24]))

  #Se crean las capas ocultas
  for i in range(0,Capas_ocultas):
    network.add(tf.keras.layers.Dense(
    units=Neur_per_layer,
    activation=ActivationHLs))

  #Se agrega la capa de salida con 4 salidas y se utiliza la función de activación softmax
  network.add(tf.keras.layers.Dense(
  units=4,
  activation="softmax"))

  #Se crea el diccionario que clasifica los pesos con su respectiva clasificación
  global class_weights
  class_weights1=dict(enumerate(class_weights))

  #Se compila la red neuronal y se asigna el optimizador Adam junto con su tasa de aprendizaje
  #También se indica que se mida la precisión en el modelo aparte de la pérdida
  if Optim==0:
    network.compile(optimizer=tf.keras.optimizers.Adam(TasaApr,use_ema=Momento),loss=lossF,metrics=["accuracy"])
  elif Optim==1:
   network.compile(optimizer=tf.keras.optimizers.SGD(TasaApr,use_ema=Momento),loss=lossF,metrics=["accuracy"])
  else:
    network.compile(optimizer=tf.keras.optimizers.Nadam(TasaApr,use_ema=Momento),loss=lossF,metrics=["accuracy"])

  #Se entrena la red neuronal con los sets de entrenamiento y validación, se asignan los pesos de clase y los callbacks
  losses = network.fit(x=X_train,y=y_train,validation_data=(X_test,y_test),epochs=NEpochs, verbose=False,class_weight=class_weights1,callbacks=callbacks)
  #network.load_weights('/content/checkpoint') #Se le cargan a la red neuronal los pesos de la mejor época
  loss_df = pd.DataFrame(losses.history) #Se convierte la historia de pérdidas y precisión en un dataframe
  #==============================================================================================================================
  val_loss_series = pd.Series(losses.history['val_loss'])

  # Encontrar la época con la menor pérdida de validación
  best_epoch = val_loss_series.idxmin()

  # Obtener la pérdida y precisión de entrenamiento en la mejor época
  train_loss = losses.history['loss'][best_epoch]
  train_acc = losses.history['accuracy'][best_epoch]

  # Obtener la pérdida y precisión de validación en la mejor época
  validation_loss = losses.history['val_loss'][best_epoch]
  validation_acc = losses.history['val_accuracy'][best_epoch]

  error=(train_loss-validation_loss)**2+train_loss
  calidad=[error,]
  return [error,]
  #Profe: Todo bien con esto

def plot_stats(gen, std):
 fig, ax1 = plt.subplots()
 line = ax1.plot(gen, std, "b-", label="Standard Deviation")
 ax1.set_xlabel("Generation")
 ax1.set_ylabel("Standard Deviation")
 labs = [l.get_label() for l in line]
 ax1.legend(line, labs, loc="center right")
 plt.show()

def plot_stats2(gen, Fmax):
 fig, ax1 = plt.subplots()
 line = ax1.plot(gen, Fmax, "b-", label="Quality")
 ax1.set_xlabel("Generation")
 ax1.set_ylabel("Quality")
 labs = [l.get_label() for l in line]
 ax1.legend(line, labs, loc="center right")
 plt.show()




#===============================Inicio evolutivo========================================================

toolbox = base.Toolbox()
# El fitness que manejará el toolbox será una función con el peso 1
# (maximización con peso unitario para cada atributo)
creator.create('FitnessMin', base.Fitness, weights=(-1.0,))
# -El individuo que manejará el toolbox será un array de floats
creator.create('Individuo', array.array, fitness=creator.FitnessMin, typecode='f')
# Registro de la función de evaluación, usando lo definido previamente en el código
toolbox.register('evaluate',RedNeuronalQual)

toolbox.register("atributo1", random.randint, a=1,b=6)
toolbox.register("atributo2", random.randint, a=1,b=14)
toolbox.register("atributo3", random.uniform, a=0.00001,b=0.5)
toolbox.register("atributo4", random.randint, a=0,b=2)
toolbox.register("atributo5", random.randint, a=0,b=1)


toolbox.register("individuo_gen", tools.initCycle, creator.Individuo, (toolbox.atributo1,toolbox.atributo2,
                                                                       toolbox.atributo3,toolbox.atributo4,
                                                                       toolbox.atributo5
                                                                       ), n=1)
# Se genera un atributo de float al azar 3 veces, y se guarda en un Individuo
# Luego, se registra en toolbox una operación para crear la población
toolbox.register('Poblacion', tools.initRepeat, list,
toolbox.individuo_gen, n=15)
# Para ello, llama unas 30 veces a la función 'individuo_gen', de manera que
# queda generada una población de 'Individuo's.
# Se utiliza la función registrada para generar una población
"""
cpu_count = multiprocessing.cpu_count()
print(f"CPU count: {cpu_count}")
pool = multiprocessing.Pool(cpu_count)
toolbox.register("map", pool.map)
"""

popu = toolbox.Poblacion()
# Método de cruce de dos puntos
toolbox.register('mate', tools.cxTwoPoint)
#Función de mutación definida en bloque anterior, con 0.05 de probabilidad
#independiente de mutación para cada uno de los genes
toolbox.register("mutate", mutacion, indpb=0.05)
# Para la mutación, se utiliza el método de torneo
toolbox.register('select', tools.selTournament, tournsize=10)
# Hall of Fame: presentación de los mejores 10 individuos
hof = tools.HallOfFame(10)

# Estadísticas del fitness general de la población
stats = tools.Statistics(lambda indiv: indiv.fitness.values)
stats.register('avg', np.mean) # Promedio de la gen
stats.register('std', np.std) # Desviación estándar de los individuos
stats.register('min', np.min) # Fitness mínimo de la gen
stats.register('max', np.max) # Fitness máximo de la gen
# Una vez que todo está registrado y establecido, ya se puede comenzar
# a correr el algoritmo evolutivo.
popu, logbook = algorithms.eaSimple(popu, toolbox, cxpb=0.2,
mutpb=0.02, ngen=5,
stats=stats,halloffame=hof,verbose=False)
#pool.close()
gen, std = logbook.select("gen", "std")
Fmax=logbook.select("max")
#print(logbook)
print(hof)
#=================================Evaluación del mejor individuo======================
#Cambiar esto a los mejores 5 individuos o algo así, pero por mientras solo 1 para ver
#que todo funciona

Capas_ocultas=int(hof[0][0]) #Se definen las capas capas intermedias (2,3,4) y su cantidad de neuronas
Neur_per_layer=int(hof[0][1])
TasaApr=hof[0][2] #Tasa de aprendizaje
Optim=int(hof[0][3])
Momento=bool(hof[0][4])

ActivationHLs="sigmoid" #Función de activación a utilizar en todas las capas ocultas
NEpochs=200 #Cantidad de épocas para entrenamiento
lossF="categorical_crossentropy" #Función de pérdida

#Se definen los callbacks, estos son los responsables de las técnicas de
#Early stopping y el guardado de pesos de la mejor época
callbacks = [
    tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=0.2*NEpochs)
    ]
#Se crea el modelo de red neuronal
network = tf.keras.models.Sequential()

#Se agrega la capa de entrada a la red con 90 entradas
network.add(tf.keras.layers.Dense(
units=Neur_per_layer,
input_shape=[24]))

#Se crean las capas ocultas
for i in range(0,Capas_ocultas):
  network.add(tf.keras.layers.Dense(
  units=Neur_per_layer,
  activation=ActivationHLs))

#Se agrega la capa de salida con 4 salidas y se utiliza la función de activación softmax
network.add(tf.keras.layers.Dense(
units=4,
activation="softmax"))

#Se crea el diccionario que clasifica los pesos con su respectiva clasificación
class_weights=dict(enumerate(class_weights))

#Se compila la red neuronal y se asigna el optimizador Adam junto con su tasa de aprendizaje
#También se indica que se mida la precisión en el modelo aparte de la pérdida
if Optim==0:
  Optim=tf.keras.optimizers.Adam(TasaApr,use_ema=Momento)
elif Optim==1:
  Optim=tf.keras.optimizers.SGD(TasaApr,use_ema=Momento)
else:
  Optim=tf.keras.optimizers.Nadam(TasaApr,use_ema=Momento)

network.compile(optimizer=Optim,loss=lossF,metrics=["accuracy"])

#Se entrena la red neuronal con los sets de entrenamiento y validación, se asignan los pesos de clase y los callbacks
losses = network.fit(x=X_train,y=y_train,validation_data=(X_test,y_test),epochs=NEpochs,class_weight=class_weights,callbacks=callbacks)
#network.load_weights('/content/checkpoint') #Se le cargan a la red neuronal los pesos de la mejor época
loss_df = pd.DataFrame(losses.history) #Se convierte la historia de pérdidas y precisión en un dataframe
#===============================================================================================================================================

gen, std = logbook.select("gen", "std")
avg=logbook.select("avg")
plot_stats2(gen, avg)
plot_stats(gen, std)




#======================================Graficación de las pérdidas, precisión, y modelo ================================================

loss_df.loc[:, ['loss', 'val_loss']].plot()
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.title('Training and Validation Loss')
plt.legend(['train loss', 'val loss'])
plt.show()

loss_df.loc[:, ['accuracy', 'val_accuracy']].plot()
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.title('Training and Validation Accuracy')
plt.legend(['train accuracy', 'val accuracy'])
plt.show()

plot_model(network, to_file='model_plot.png', show_shapes=True, show_layer_names=True)
#==============================================================================================================================


#================================Impresion de los datos de la mejor época registrada===========================================
val_loss_series = pd.Series(losses.history['val_loss'])

# Encontrar la época con la menor pérdida de validación
best_epoch = val_loss_series.idxmin()

# Obtener la pérdida y precisión de entrenamiento en la mejor época
train_loss = losses.history['loss'][best_epoch]
train_acc = losses.history['accuracy'][best_epoch]

# Obtener la pérdida y precisión de validación en la mejor época
validation_loss = losses.history['val_loss'][best_epoch]
validation_acc = losses.history['val_accuracy'][best_epoch]


#impresión de resultados de la epoch con menor pérdida de validación
###Esto es parte de la función de calidad, para la calidad se tienen que comparar
#Tanto las de entrenamiento como las de validación para evitar el overfitting, se puede agarrar
#un error cuadrado entre los valores de entrenamiento y validación de la mejor época y minimizar ese error
print("-------------------------------------------------------")
print("Menor pérdida de validación \n")
print("Época: ", best_epoch, "\n")

print("Durante el entranamiento: \n")
print("Pérdida: {:.3}".format(train_loss))
print("Precisión: {:.2%}".format(train_acc))
print("")
print("Durante la validación: \n")
print("Pérdida: {:.3}".format(validation_loss))
print("Precisión: {:.2%}".format(validation_acc))

print("")

