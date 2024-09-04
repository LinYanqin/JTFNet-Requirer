import tensorflow   as tf
from utils  import ComplexInit
import numpy as np
from tflearn.layers.conv import global_avg_pool

def complex_conv2d(input,name,kw=3,kh=3,n_out=32,sw=1,sh=1,activation=True):
    n_in = input.get_shape()[-1].value
    with tf.name_scope(name) as scope:
        kernel_init = ComplexInit(kernel_size=(kh,kw),
                                  input_dim=n_in,
                                  weight_dim=2,
                                  nb_filters=n_out,
                                  criterion='he')
        kernel = tf.get_variable(scope + 'weights',
                                 shape=[kh,kw,n_in,n_out],
                                 dtype=tf.float32,
                                 initializer=kernel_init)
        bias_init = tf.constant(0.0001,dtype=tf.float32,shape=[n_out*2])
        biases = tf.get_variable(scope+'biases', dtype=tf.float32, initializer=bias_init)

        conv = tf.nn.conv2d(input,kernel,strides=[1,sh,sw,1],padding='SAME')
        conv_bias = tf.nn.bias_add(conv,biases)
        if activation:
            act = tf.nn.leaky_relu(conv_bias)
            output = act

        else:
            output = conv_bias


        return output

def Conv_transpose(x, name,filter_size, in_filters, out_filters, fraction=2, padding="SAME"):
    with tf.variable_scope(name):
        n = filter_size * filter_size * out_filters
        kernel = tf.get_variable('filter', [1, filter_size, out_filters, in_filters], tf.float32,
                                 initializer=tf.random_normal_initializer(stddev=np.sqrt(2.0 / n)))
        size = tf.shape(x)
        output_shape = tf.stack([size[0], size[1], size[2] * fraction, out_filters])
        x = tf.nn.conv2d_transpose(x, kernel, output_shape, [1, fraction, fraction, 1], padding)

        return x

def real2complex(x):
    channel = x.shape[-1] // 2
    if x.shape.ndims == 3:
        return tf.complex(x[:,:,:channel], x[:,:,channel:])
    elif x.shape.ndims == 4:
        return tf.complex(x[:,:,:,:channel], x[:,:,:,channel:])

def complex2real(x):
    x_real = np.real(x)
    x_imag = np.imag(x)
    return np.concatenate([x_real,x_imag], axis=-1)

def dc(generated, X_k, mask):
    gene_complex = real2complex(generated)
    gene_complex = tf.transpose(gene_complex, [0, 3, 1, 2])
    mask = tf.transpose(mask, [0, 3, 1, 2])
    X_k = tf.transpose(X_k, [0, 3, 1, 2])
    gene_fft = tf.ifft2d(gene_complex)
    out_fft = X_k + gene_fft * (1.0 - mask)
    output_complex = tf.fft2d(out_fft)
    output_complex = tf.transpose(output_complex, [0, 2, 3, 1])
    output_real = tf.cast(tf.real(output_complex), dtype=tf.float32)
    output_imag = tf.cast(tf.imag(output_complex), dtype=tf.float32)
    output = tf.concat([output_real, output_imag], axis=-1)
    return output

def dc_tdomain(generated, X_k, mask):
    gene_t = real2complex(generated)
    out_fft = X_k + gene_t * (1.0 - mask)
    output_complex = out_fft
    output_real = tf.cast(tf.real(output_complex), dtype=tf.float32)
    output_imag = tf.cast(tf.imag(output_complex), dtype=tf.float32)
    output = tf.concat([output_real,output_imag], axis=-1)
    return output

def complex_real(x):
    output_real = tf.cast(tf.real(x), dtype=tf.float32)
    output_imag = tf.cast(tf.imag(x), dtype=tf.float32)
    output = tf.concat([output_real, output_imag], axis=-1)
    return output
#X_K是时域采样后的数据

def getModel(x, x_dc, mask):

    conv1_SDN0 = complex_conv2d(x, 'conv1_SDN0', kw=3, kh=3, n_out=16, sw=2, sh=2, activation=True)
    conv2_SDN0 = complex_conv2d(conv1_SDN0, 'conv2_SDN0', kw=3, kh=3, n_out=32, sw=2, sh=2, activation=True)
    conv3_SDN0 = complex_conv2d(conv2_SDN0, 'conv3_SDN0', kw=3, kh=3, n_out=64, sw=2, sh=2, activation=True)
    deconv3_SDN0 = Conv_transpose(conv3_SDN0, 'deconv3_SDN0', filter_size=3, in_filters=128, out_filters=64)
    SDN0_up2 = tf.concat([deconv3_SDN0, conv2_SDN0], axis=3, name='SDN0_up2')
    deconv2_SDN0 = Conv_transpose(SDN0_up2, 'deconv2_SDN0', filter_size=3, in_filters=128, out_filters=32)
    SDN0_up1 = tf.concat([deconv2_SDN0, conv1_SDN0], axis=3, name='SDN0_up1')
    deconv1_SDN0 = Conv_transpose(SDN0_up1, 'deconv1_SDN0', filter_size=3, in_filters=64, out_filters=2)
    block_SDN0 = deconv1_SDN0 + x
    k_temp_real = dc_tdomain(block_SDN0, x_dc, mask)

    k_temp1 = real2complex(k_temp_real)
    k_temp = tf.transpose(k_temp1, [0, 3, 1, 2])
    temp = tf.fft(k_temp)
    temp= tf.transpose(temp, [0, 2, 3, 1])
    #SDN1
    temp_1 = complex_real(temp)
    conv1_SDN1 = complex_conv2d(temp_1, 'conv1_SDN1', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    conv2_SDN1 = complex_conv2d(conv1_SDN1, 'conv2_SDN1', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    conv3_SDN1 = complex_conv2d(conv2_SDN1, 'conv3_SDN1', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    deconv3_SDN1 = Conv_transpose(conv3_SDN1, 'deconv3_SDN1', filter_size=3, in_filters=128, out_filters=64)
    SDN1_up2 = tf.concat([deconv3_SDN1, conv2_SDN1], axis=3, name='SDN1_up2')
    deconv2_SDN1 = Conv_transpose(SDN1_up2, 'deconv2_SDN1', filter_size=3, in_filters=128, out_filters=32)
    SDN1_up1 = tf.concat([deconv2_SDN1, conv1_SDN1], axis=3, name='SDN1_up1')
    deconv1_SDN1 = Conv_transpose(SDN1_up1, 'deconv1_SDN1', filter_size=3, in_filters=64, out_filters=2)
    block_SDN1 = deconv1_SDN1 + temp_1
    temp_SDN1 = dc(block_SDN1, x_dc, mask)
    #SDN2
    conv1_SDN2 = complex_conv2d(temp_SDN1, 'conv1_SDN2', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    conv2_SDN2 = complex_conv2d(conv1_SDN2, 'conv2_SDN2', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    conv3_SDN2 = complex_conv2d(conv2_SDN2, 'conv3_SDN2', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    deconv3_SDN2 = Conv_transpose(conv3_SDN2, 'deconv3_SDN2', filter_size=3, in_filters=128, out_filters=64)
    SDN2_up2 = tf.concat([deconv3_SDN2, conv2_SDN2], axis=3, name='SDN2_up2')
    deconv2_SDN2 = Conv_transpose(SDN2_up2, 'deconv2_SDN2', filter_size=3, in_filters=128, out_filters=32)
    SDN2_up1 = tf.concat([deconv2_SDN2, conv1_SDN2], axis=3, name='SDN2_up1')
    deconv1_SDN2 = Conv_transpose(SDN2_up1, 'deconv1_SDN2', filter_size=3, in_filters=64, out_filters=2)
    block_SDN2 = deconv1_SDN2 + temp_SDN1
    temp_SDN2 = dc(block_SDN2, x_dc, mask)
    #SDN3
    conv1_SDN3 = complex_conv2d(temp_SDN2, 'conv1_SDN3', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    conv2_SDN3 = complex_conv2d(conv1_SDN3, 'conv2_SDN3', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    conv2_dropout = tf.nn.dropout(conv2_SDN3, keep_prob=0.5)
    conv3_SDN3 = complex_conv2d(conv2_dropout, 'conv3_SDN3', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    deconv3_SDN3 = Conv_transpose(conv3_SDN3, 'deconv3_SDN3', filter_size=3, in_filters=128, out_filters=64)
    SDN3_up2 = tf.concat([deconv3_SDN3, conv2_SDN3], axis=3, name='SDN3_up2')
    deconv2_SDN3 = Conv_transpose(SDN3_up2, 'deconv2_SDN3', filter_size=3, in_filters=128, out_filters=32)
    SDN3_up1 = tf.concat([deconv2_SDN3, conv1_SDN3], axis=3, name='SDN3_up1')
    deconv1_SDN3 = Conv_transpose(SDN3_up1, 'deconv1_SDN3', filter_size=3, in_filters=64, out_filters=2)
    block_SDN3 = deconv1_SDN3 + temp_SDN2
    temp_SDN3 = dc(block_SDN3, x_dc, mask)
    #SDN4
    conv1_SDN4 = complex_conv2d(temp_SDN3, 'conv1_SDN4', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    conv2_SDN4 = complex_conv2d(conv1_SDN4, 'conv2_SDN4', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    conv2_dropout = tf.nn.dropout(conv2_SDN4, keep_prob=0.5)
    conv3_SDN4 = complex_conv2d(conv2_dropout, 'conv3_SDN4', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    deconv3_SDN4 = Conv_transpose(conv3_SDN4, 'deconv3_SDN4', filter_size=3, in_filters=128, out_filters=64)
    SDN4_up2 = tf.concat([deconv3_SDN4, conv2_SDN4], axis=3, name='SDN4_up2')
    deconv2_SDN4 = Conv_transpose(SDN4_up2, 'deconv2_SDN4', filter_size=3, in_filters=128, out_filters=32)
    SDN4_up1 = tf.concat([deconv2_SDN4, conv1_SDN4], axis=3, name='SDN4_up1')
    deconv1_SDN4 = Conv_transpose(SDN4_up1, 'deconv1_SDN4', filter_size=3, in_filters=64, out_filters=2)
    block_SDN4 = deconv1_SDN4 + temp_SDN3
    temp_SDN4 = dc(block_SDN4, x_dc, mask)
    #SDN5
    conv1_SDN5 = complex_conv2d(temp_SDN4, 'conv1_SDN5', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    conv2_SDN5 = complex_conv2d(conv1_SDN5, 'conv2_SDN5', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    conv3_SDN5 = complex_conv2d(conv2_SDN5, 'conv3_SDN5', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    deconv3_SDN5 = Conv_transpose(conv3_SDN5, 'deconv3_SDN5', filter_size=3, in_filters=128, out_filters=64)
    SDN5_up2 = tf.concat([deconv3_SDN5, conv2_SDN5], axis=3, name='SDN5_up2')
    deconv2_SDN5 = Conv_transpose(SDN5_up2, 'deconv2_SDN5', filter_size=3, in_filters=128, out_filters=32)
    SDN5_up1 = tf.concat([deconv2_SDN5, conv1_SDN5], axis=3, name='SDN5_up1')
    deconv1_SDN5 = Conv_transpose(SDN5_up1, 'deconv1_SDN5', filter_size=3, in_filters=64, out_filters=2)
    block_SDN5 = deconv1_SDN5 + temp_SDN4
    temp_SDN5 = dc(block_SDN5, x_dc, mask)
    # #SDN6
    conv1_SDN6 = complex_conv2d(temp_SDN5, 'conv1_SDN6', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    conv2_SDN6 = complex_conv2d(conv1_SDN6, 'conv2_SDN6', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    conv2_dropout = tf.nn.dropout(conv2_SDN6, keep_prob=0.5)
    conv3_SDN6 = complex_conv2d(conv2_dropout, 'conv3_SDN6', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    deconv3_SDN6 = Conv_transpose(conv3_SDN6, 'deconv3_SDN6', filter_size=3, in_filters=128, out_filters=64)
    SDN6_up2 = tf.concat([deconv3_SDN6, conv2_SDN6], axis=3, name='SDN6_up2')
    deconv2_SDN6 = Conv_transpose(SDN6_up2, 'deconv2_SDN6', filter_size=3, in_filters=128, out_filters=32)
    SDN6_up1 = tf.concat([deconv2_SDN6, conv1_SDN6], axis=3, name='SDN6_up1')
    deconv1_SDN6 = Conv_transpose(SDN6_up1, 'deconv1_SDN6', filter_size=3, in_filters=64, out_filters=2)
    block_SDN6 = deconv1_SDN6 + temp_SDN5
    temp_SDN6 = dc(block_SDN6, x_dc, mask)

    # conv1_SDN7 = complex_conv2d(temp_SDN6, 'conv1_SDN7', kw=3, kh=1, n_out=16, sw=2, sh=1, activation=True)
    # conv2_SDN7 = complex_conv2d(conv1_SDN7, 'conv2_SDN7', kw=3, kh=1, n_out=32, sw=2, sh=1, activation=True)
    # conv2_dropout = tf.nn.dropout(conv2_SDN7, keep_prob=0.5)
    # conv3_SDN7 = complex_conv2d(conv2_dropout, 'conv3_SDN7', kw=3, kh=1, n_out=64, sw=2, sh=1, activation=True)
    # deconv3_SDN7 = Conv_transpose(conv3_SDN7, 'deconv3_SDN7', filter_size=3, in_filters=128, out_filters=64)
    # SDN7_up2 = tf.concat([deconv3_SDN7, conv2_SDN7], axis=3, name='SDN7_up2')
    # deconv2_SDN7 = Conv_transpose(SDN7_up2, 'deconv2_SDN7', filter_size=3, in_filters=128, out_filters=32)
    # SDN7_up1 = tf.concat([deconv2_SDN7, conv1_SDN7], axis=3, name='SDN7_up1')
    # deconv1_SDN7 = Conv_transpose(SDN7_up1, 'deconv1_SDN7', filter_size=3, in_filters=64, out_filters=2)
    # block_SDN7 = deconv1_SDN7 + temp_SDN6
    # temp_SDN7= dc(block_SDN7, x_dc, mask)
    conv1_out1 = complex_conv2d(block_SDN6, 'conv_final1', kw=3, kh=3, n_out=16, sw=1, sh=1, activation=True)
    conv1_out2 = complex_conv2d(conv1_out1, 'conv_final2', kw=3, kh=3, n_out=1, sw=1, sh=1, activation=True)

    deconv3_SDN6_var = Conv_transpose(conv3_SDN6, 'deconv3_SDN6_var', filter_size=3, in_filters=128, out_filters=64)
    deconv2_SDN6_var = Conv_transpose(deconv3_SDN6_var, 'deconv2_SDN6_var', filter_size=3, in_filters=64, out_filters=32)
    var = Conv_transpose(deconv2_SDN6_var, 'deconv1_SDN6_var', filter_size=3, in_filters=32, out_filters=2)
    return temp_SDN4, temp_SDN5, temp_SDN6, conv1_out2, k_temp_real, var