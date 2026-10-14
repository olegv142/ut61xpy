"""
Termocouple conversion functions
"""

import math

def poly(arg, coef):
    """Calculate polynomial given argument and the list of coefficients"""
    val = 0
    for c in reversed(coef):
        val *= arg
        val += c
    return val

def K_mv2C(mv):
    """Convert millivolts to °C for K-type termocouple"""
    if mv <= 0:
        return poly(mv, (0, 25.173462, -1.1662878, -1.0833638, -8.9773540E-01, -3.7342377E-01, -8.6632643E-02, -1.0450598E-02, -5.1920577E-04))
    if mv < 20.644:
        return poly(mv, (0, 25.08355, 7.860106E-02, -2.503131E-01, 8.315270E-02, -1.228034E-02, 9.804036E-04, -4.413030E-05, 1.057734E-06, -1.052755E-08))
    else:
        return poly(mv, (-131.8058, 48.30222, -1.646031E+00, 5.464731E-02, -9.650715E-04, 8.802193E-06, -3.110810E-08))

def K_C2mv(t):
    """Convert °C to millivolts for K-type termocouple"""
    if t <= 0:
        return poly(t, (0, 0.0394501280250,
                0.236223735980E-04, -0.328589067840E-06, -0.499048287770E-08,
                -0.675090591730E-10, -0.574103274280E-12, -0.310888728940E-14,
                -0.104516093650E-16, -0.198892668780E-19, -0.163226974860E-22
            ))
    return poly(t, (-0.176004136860E-01,
            0.389212049750E-01, 0.185587700320E-04, -0.994575928740E-07,
            0.318409457190E-09, -0.560728448890E-12, 0.560750590590E-15,
            -0.320207200030E-18, 0.971511471520E-22, -0.121047212750E-25
        )) + 0.1185976 * math.exp(-0.1183432E-03*(t - 126.9686)**2)

def K_delta_mv2C(delta_mv, Tref):
    """Convert measured termocouple voltage (in millivolts) to °C given the reference junction temperature (in °C)"""
    mv_ref = K_C2mv(Tref)
    return K_mv2C(mv_ref + delta_mv)

if __name__ == '__main__':
    import numpy as np
    import matplotlib.pyplot as plt

    T = np.arange(-200, 1372)
    e = max(abs(K_mv2C(K_C2mv(t)) - t) for t in T)
    print('max temp error:', e)

    V = np.arange(-6, 54, .1)
    T = [K_mv2C(v) for v in V]
    plt.plot(V, T)
    plt.show()

