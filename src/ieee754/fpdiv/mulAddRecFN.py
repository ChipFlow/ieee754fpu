"""
/*============================================================================

This Verilog source file is part of the Berkeley HardFloat IEEE Floating-Point
Arithmetic Package, Release 1, by John R. Hauser.

Copyright 2019 The Regents of the University of California.  All rights
reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

 1. Redistributions of source code must retain the above copyright notice,
    this list of conditions, and the following disclaimer.

 2. Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions, and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

 3. Neither the name of the University nor the names of its contributors may
    be used to endorse or promote products derived from this software without
    specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS "AS IS", AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE, ARE
DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

=============================================================================*/

`include "HardFloat_consts.vi"
`include "HardFloat_specialize.vi"

"""

from nmigen import Elaboratable, Cat, Const, Mux, Module, Signal, Repl
from nmutil.concurrentunit import num_bits

#/*----------------------------------------------------------------------------
#*----------------------------------------------------------------------------*/

class mulAddRecFNToRaw_preMul(Elaboratable):
    def __init__(self, expWidth=3, sigWidth=3):
        # inputs
        self.control = Signal(floatControlWidth, reset_less=True)
        self.op = Signal(2, reset_less=True)
        self.a = Signal(expWidth + sigWidth + 1, reset_less=True)
        self.b = Signal(expWidth + sigWidth + 1, reset_less=True)
        self.c = Signal(expWidth + sigWidth + 1, reset_less=True)
        self.roundingMode = Signal(3, reset_less=True)

        # outputs
        self.mulAddA = Signal(sigWidth, reset_less=True)
        self.mulAddB = Signal(sigWidth, reset_less=True)
        self.mulAddC = Signal(sigWidth*2, reset_less=True)
        self.intermed_compactState = Signal(6, reset_less=True)
        self.intermed_sExp = Signal(expWidth + 2, reset_less=True)
        wid = num_bits(sigWidth + 1)
        self.intermed_CDom_CAlignDist = Signal(wid, reset_less=True)
        self.intermed_highAlignedSigC = Signal((sigWidth + 2), reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        #/*-------------------------------------------------------------------
        #*--------------------------------------------------------------------*/
        prodWidth = sigWidth*2;
        sigSumWidth = sigWidth + prodWidth + 3;
        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        isNaNA = Signal(reset_less=True)
        isInfA = Signal(reset_less=True)
        isZeroA = Signal(reset_less=True)
        signA = Signal(reset_less=True)

        sExpA = Signal((expWidth + 2, True), reset_less=True)
        sigA = Signal(sigWidth+1, reset_less=True)
        m.submodules.recFNToRawFN_a = rf = recFNToRawFN(expWidth, sigWidth)
        comb += [(a, isNaNA, isInfA, isZeroA, signA, sExpA, sigA)]

        isSigNaNA = Signal(reset_less=True)
        m.submodules.isSigNaN_a = nan_a = isSigNaNRecFN(expWidth, sigWidth)
        comb += [(a, isSigNaNA)]

        isNaNB = Signal(reset_less=True)
        isInfB = Signal(reset_less=True)
        isZeroB = Signal(reset_less=True)
        signB = Signal(reset_less=True)

        sExpB = Signal((expWidth + 2, True), reset_less=True)
        sigB = Signal(sigWidth+1, reset_less=True)
        m.submodules.recFNToRawFN_b = rf = recFNToRawFN(expWidth, sigWidth)
        comb += [(b, isNaNB, isInfB, isZeroB, signB, sExpB, sigB)]

        isSigNaNB = Signal(reset_less=True)
        m.submodules.isSigNaN_b = nan_b = isSigNaNRecFN(expWidth, sigWidth)
        comb += [(b, isSigNaNB)]

        isNaNC = Signal(reset_less=True)
        isInfC = Signal(reset_less=True)
        isZeroC = Signal(reset_less=True)
        signC = Signal(reset_less=True)

        sExpC = Signal((expWidth + 2, True), reset_less=True)
        sigC = Signal(sigWidth+1, reset_less=True)
        m.submodules.recFNToRawFN_c = rf = recFNToRawFN(expWidth, sigWidth)
        comb += [(c, isNaNC, isInfC, isZeroC, signC, sExpC, sigC)]

        isSigNaNC = Signal(reset_less=True)
        m.submodules.isSigNaN_c = nan_c = isSigNaNRecFN(expWidth, sigWidth)
        comb += [(c, isSigNaNC)]

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        signProd = Signal(reset_less=True)
        sExpAlignedProd = Signal((expWidth + 3, True), reset_less=True)
        doSubMags = Signal(reset_less=True)
        opSignC = Signal(reset_less=True)
        roundingMode_min = Signal(reset_less=True)

        comb += signProd.eq(signA ^ signB ^ op[1])
        comb += sExpAlignedProd.eq(sExpA + sExpB + \
                                    (-(1<<expWidth) + sigWidth + 3))
        comb += doSubMags.eq(signProd ^ signC ^ op[0])
        comb += opSignC.eq(signProd ^ doSubMags)
        comb += roundingMode_min.eq(roundingMode == ROUND_MIN)

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        sNatCAlignDist = Signal((expWidth + 3, True), reset_less=True)
        posNatCAlignDist = Signal(expWidth + 2, reset_less=True)
        isMinCAlign = Signal(reset_less=True)
        CIsDominant = Signal(reset_less=True)
        sExpSum = Signal((expWidth + 2, True), reset_less=True)
        CAlignDist = Signal(num_bits(sigSumWidth), reset_less=True)
        extComplSigC = Signal((sigSumWidth + 3, True), reset_less=True)
        mainAlignedSigC = Signal(sigSumWidth + 2, reset_less=True)

        CGrainAlign = (sigSumWidth - sigWidth - 1) & 3;
        grainAlignedSigC = Signal(sigWidth+CGrainAlign + 1, reset_less=True)
        reduced4SigC = Signal((sigWidth+CGrainAlign)/4 + 1, reset_less=True)
        m.submodules.compressBy4_sigC = compressBy4(sigWidth + 1 + CGrainAlign)
        comb += (grainAlignedSigC, reduced4SigC)
        CExtraMaskHiBound = (sigSumWidth - 1)/4;
        CExtraMaskLoBound = (sigSumWidth - sigWidth - 1)/4;
        CExtraMask = Signal(CExtraMaskHiBound - CExtraMaskLoBound,
                            reset_less=True)
        m.submodules.lowMask_CExtraMask = lowMaskHiLo(clog2(sigSumWidth) - 2,
                                                      CExtraMaskHiBound, 
                                                      CExtraMaskLoBound)
        comb += (CAlignDist[(clog2(sigSumWidth) - 1):2], CExtraMask)
        reduced4CExtra = Signal(reset_less=True)
        alignedSigC = Signal(sigSumWidth, reset_less=True)

        sc = [Repl(doSubMags, sigSumWidth - sigWidth + 2)] + \
                            [Mux(doSubMags, ~sigC, sigC)]

        comb += [\
            sNatCAlignDist.eq(sExpAlignedProd - sExpC),
            posNatCAlignDist.eq(sNatCAlignDist[:expWidth + 2]),
            isMinCAlign.eq(isZeroA | isZeroB | (sNatCAlignDist < 0)),
            CIsDominant.eq(~isZeroC & \
                           (isMinCAlign | (posNatCAlignDist <= sigWidth))),
            sExpSum.eq(Mux(CIsDominant, sExpC, sExpAlignedProd - sigWidth)),
            CAlignDist.eq(Mux(isMinCAlign, 0,
                              Mux((posNatCAlignDist < sigSumWidth - 1),
                                  posNatCAlignDist[:num_bits(sigSumWidth)],
                                  sigSumWidth - 1))),
            extComplSigC.eq(Cat(*sc)),
            mainAlignedSigC.eq(extComplSigC >> CAlignDist),
            grainAlignedSigC.eq(sigC<<CGrainAlign),
            compressBy4_sigC.inp.eq(grainAlignedSigC),
            reduced4SigC.eq(compressBy4_sigC.out),
            lowMaskHiLo.inp.eq(CAlignDist[2:clog2(sigSumWidth)]),
            CExtraMask.eq(lowMaskHiLo.out),
            reduced4CExtra.eq((reduced4SigC & CExtraMask).bool()),
            alignedSigC.eq(Cat(\
                 Mux(doSubMags, (mainAlignedSigC[:3]&0b111) & ~reduced4CExtra,
                                (mainAlignedSigC[:3].bool()) | reduced4CExtra),
                     mainAlignedSigC>>3)),
        ]

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        isNaNAOrB = Signal(reset_less=True)
        isNaNAny = Signal(reset_less=True)
        isInfAOrB = Signal(reset_less=True)
        invalidProd = Signal(reset_less=True)
        notSigNaN_invalidExc = Signal(reset_less=True)
        invalidExc = Signal(reset_less=True)
        notNaN_addZeros = Signal(reset_less=True)
        specialCase = Signal(reset_less=True)
        specialNotNaN_signOut = Signal(reset_less=True)
        comb += [
            isNaNAOrB.eq(isNaNA | isNaNB),
            isNaNAny.eq(isNaNAOrB | isNaNC),
            isInfAOrB.eq(isInfA | isInfB),
            invalidProd.eq((isInfA & isZeroB) | (isZeroA & isInfB)),
            notSigNaN_invalidExc.eq(
                invalidProd | (~isNaNAOrB & isInfAOrB & isInfC & doSubMags)),
            invalidExc.eq(
                isSigNaNA | isSigNaNB | isSigNaNC | notSigNaN_invalidExc),
            notNaN_addZeros.eq((isZeroA | isZeroB) & isZeroC),
            specialCase.eq(isNaNAny | isInfAOrB | isInfC | notNaN_addZeros),
            specialNotNaN_signOut.eq(
            (isInfAOrB & signProd) | (isInfC & opSignC)
                | (notNaN_addZeros & ~roundingMode_min & signProd & opSignC)
                | (notNaN_addZeros & roundingMode_min & (signProd | opSignC)))
        ]

        special_signOut = specialNotNaN_signOut;
        #/*-------------------------------------------------------------------
        # *-------------------------------------------------------------------*/
        comb += self.mulAddA.eq(sigA)
        comb += self.mulAddB.eq(sigB)
        comb += self.mulAddC.eq(alignedSigC[1:prodWidth+1])
        comb += self.intermed_compactState.eq(Cat(
            special_signOut,
             notNaN_addZeros     | (~specialCase & alignedSigC[0]),
             isInfAOrB | isInfC | (~specialCase & CIsDominant   ),
             isNaNAny            | (~specialCase & doSubMags     ),
             invalidExc          | (~specialCase & signProd      ),
             specialCase,))
        comb += self.intermed_sExp.eq(sExpSum)
        comb += self.intermed_CDom_CAlignDist(
                    CAlignDist[:clog2(sigWidth + 1)])
        comb += self.intermed_highAlignedSigC.eq(
              alignedSigC[(sigSumWidth - 1):(prodWidth + 1)])

        return m

#/*------------------------------------------------------------------------
#*------------------------------------------------------------------------*/

class mulAddRecFNToRaw_postMul(Elaboratable):

    def __init__(self, expWidth=3, sigWidth=3):
        # inputs
        self.intermed_compactState = Signal(6, reset_less=True)
        self.intermed_sExp = Signal(expWidth + 2, reset_less=True)
        wid = num_bits(sigWidth + 1)
        self.intermed_CDom_CAlignDist = Signal(wid, reset_less=True)
        self.intermed_highAlignedSigC = Signal((sigWidth + 2), reset_less=True)
        self.mulAddResult = Signal(sigWidth*2, reset_less=True)
        self.roundingMode = Signal(3, reset_less=True)

        # outputs
        self.invalidExc = Signal(reset_less=True)
        self.out_isNaN = Signal(reset_less=True)
        self.out_isInf = Signal(reset_less=True)
        self.out_isZero = Signal(reset_less=True)
        self.out_sign = Signal(reset_less=True)
        self.out_sExp = Signal((expWidth + 2, True), reset_less=True)
        self.out_sig = Signal(sigWidth + 3, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        prodWidth = sigWidth*2;
        sigSumWidth = sigWidth + prodWidth + 3;

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        specialCase     = Signal(reset_less=True)
        invalidExc    = Signal(reset_less=True)
        out_isNaN     = Signal(reset_less=True)
        out_isInf     = Signal(reset_less=True)
        notNaN_addZeros = Signal(reset_less=True)
        signProd        = Signal(reset_less=True)
        doSubMags       = Signal(reset_less=True)
        CIsDominant     = Signal(reset_less=True)
        bit0AlignedSigC = Signal(reset_less=True)
        special_signOut = Signal(reset_less=True)
        comb += [
            specialCase     .eq( intermed_compactState[5] ),
            invalidExc    .eq( specialCase & intermed_compactState[4] ),
            out_isNaN     .eq( specialCase & intermed_compactState[3] ),
            out_isInf     .eq( specialCase & intermed_compactState[2] ),
            notNaN_addZeros .eq( specialCase & intermed_compactState[1] ),
            signProd        .eq( intermed_compactState[4] ),
            doSubMags       .eq( intermed_compactState[3] ),
            CIsDominant     .eq( intermed_compactState[2] ),
            bit0AlignedSigC .eq( intermed_compactState[1] ),
            special_signOut .eq( intermed_compactState[0] ),
        ]

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        opSignC = Signal(reset_less=True)
        incHighAlignedSigC = Signal(sigWidth + 3, reset_less=True)
        sigSum = Signal(sigSumWidth, reset_less=True)
        roundingMode_min = Signal(reset_less=True)

        comb += [\
            opSignC.eq(signProd ^ doSubMags),
            incHighAlignedSigC.eq(intermed_highAlignedSigC + 1),
            sigSum.eq(Cat(bit0AlignedSigC,
                          mulAddResult[(prodWidth - 1):0],
                          Mux(mulAddResult[prodWidth],
                              incHighAlignedSigC,
                              intermed_highAlignedSigC))),
            roundingMode_min.eq(roundingMode == ROUND_MIN),
        ]

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        CDom_sign = Signal(reset_less=True)
        CDom_sExp = Signal((expWidth + 2, True), reset_less=True)
        CDom_absSigSum = Signal(prodWidth+2, reset_less=True)
        CDom_absSigSumExtra = Signal(reset_less=True)
        CDom_mainSig = Signal(sigWidth+5, reset_less=True)
        CDom_grainAlignedLowSig = Signal(sigWidth | 3, reset_less=True)
        CDom_reduced4LowSig = Signal(sigWidth/4+1, reset_less=True)
        CDom_sigExtraMask = Signal(sigWidth/4, reset_less=True)

        lowMask_CDom_sigExtraMask = lm
        m.submodules.lm = lm = lowMaskLoHi(clog2(sigWidth + 1) - 2, 0,
                                           sigWidth/4)
        CDom_reduced4SigExtra = Signal(reset_less=True)
        CDom_sig = Signal(sigWidth+3, reset_less=True)

        comb += [\
            CDom_sign.eq(opSignC),
            CDom_sExp.eq(intermed_sExp - doSubMags),
            CDom_absSigSum.eq(Mux(doSubMags,
                                  ~sigSum[sigWidth+1:sigSumWidth],
                Cat(sigSum[sigWidth+2 : sigSumWidth - 2],
                    intermed_highAlignedSigC[(sigWidth + 1):sigWidth],
                    0b0))),
            CDom_absSigSumExtra.eq(Mux(doSubMags,
                          (~sigSum[1:sigWidth+1]).bool(),
                          sigSum[1:sigWidth + 2].bool())),
            CDom_mainSig.eq(
                (CDom_absSigSum<<intermed_CDom_CAlignDist)>>(sigWidth - 3)),
            CDom_grainAlignedLowSig.eq(
                    CDom_absSigSum[(sigWidth - 1):0]<<(~sigWidth & 3)),
            CDom_reduced4LowSig.eq(compressBy4_CDom_absSigSum.out),
            compressBy4_CDom_absSigSum.inp.eq(CDom_grainAlignedLowSig),
            lowMask_CDom_sigExtraMask.inp.eq(
                intermed_CDom_CAlignDist[2:clog2(sigWidth + 1)]),
            CDom_sigExtraMask.eq(lowMask_CDom_sigExtraMask.out),
            CDom_reduced4SigExtra.eq(
                    (CDom_reduced4LowSig & CDom_sigExtraMask).bool()),
            CDom_sig.eq(Cat((CDom_mainSig[:3]).bool() | 
                             CDom_reduced4SigExtra | 
                             CDom_absSigSumExtra,
                            CDom_mainSig>>3)),
        ]

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        notCDom_signSigSum = Signal(reset_less=True)
        notCDom_absSigSum = Signal(prodWidth + 3, reset_less=True)
        notCDom_reduced2AbsSigSum = Signal((prodWidth+2)//2+1, reset_less=True)
        m.submodules.cb2 = compressBy2_notCDom_absSigSum = \
                compressBy2(prodWidth + 3)
        notCDom_normDistReduced2 = Signal(clog2(prodWidth+4) - 1,
                                         reset_less=True)
        m.submodules.clz = countLeadingZeros_notCDom = \
                countLeadingZeros((prodWidth + 2)/2 + 1,
                                  clog2(prodWidth + 4) - 1)
        notCDom_nearNormDist = Signal(clog2(prodWidth + 4), reset_less=True)
        notCDom_sExp = Signal((expWidth + 2, True), reset_less=True)
        notCDom_mainSig = Signal(sigWidth + 5, reset_less=True)
        sw = (sigWidth/2 + 1) | 1
        CDom_grainAlignedLowReduced2Sig = Signal(sw, reset_less=True)
        notCDom_reduced4AbsSigSum = Signal((sigWidth + 2)//4+1, reset_less=True)
        m.submodules.cb2r = compressBy2_notCDom_reduced2AbsSigSum = \
                                compressBy2(sw)
        sw = (sigWidth + 2)//4
        notCDom_sigExtraMask = Signal(sw, reset_less=True)
        m.submodules.lms = lowMask_notCDom_sigExtraMask = \
                lowMaskLoHi(clog2(prodWidth + 4) - 2, 0, sw)
        notCDom_reduced4SigExtra = Signal(reset_less=True)
        notCDom_sig = Signal(sigWidth+3, reset_less=True)
        notCDom_completeCancellation = Signal(reset_less=True)
        notCDom_sign = Signal(reset_less=True)

        comb += [\
            notCDom_signSigSum.eq(sigSum[prodWidth + 3]),
            notCDom_absSigSum.eq(Mux(notCDom_signSigSum,
                                    ~sigSum[:prodWidth + 3],
                                    sigSum[:prodWidth + 3] + doSubMags)),
            compressBy2_notCDom_absSigSum.inp.eq(notCDom_absSigSum),
            notCDom_reduced2AbsSigSum.eq(compressBy2_notCDom_absSigSum.out),
            countLeadingZeros_notCDom.inp.eq(notCDom_reduced2AbsSigSum),
            notCDom_normDistReduced2.out.eq(countLeadingZeros_notCDom),
            notCDom_nearNormDist.eq(notCDom_normDistReduced2<<1),
            notCDom_sExp.eq(intermed_sExp - notCDom_nearNormDist),
            notCDom_mainSig.eq((Cat(notCDom_absSigSum, 0)<<
                                    notCDom_nearNormDist)>>(sigWidth - 1)),
            CDom_grainAlignedLowReduced2Sig.eq(
                notCDom_reduced2AbsSigSum[sigWidth/2:0]<<((sigWidth/2) & 1)),
            compressBy2_notCDom_reduced2AbsSigSum.inp.eq(
                            CDom_grainAlignedLowReduced2Sig),
            compressBy2_notCDom_reduced2AbsSigSum.eq(
                            notCDom_reduced4AbsSigSum.out),
            lowMask_notCDom_sigExtraMask.inp.eq(
                notCDom_normDistReduced2[1:clog2(prodWidth + 4) - 1]),
            notCDom_sigExtraMask.eq(lowMask_notCDom_sigExtraMask.out),
            notCDom_reduced4SigExtra.eq(
                (notCDom_reduced4AbsSigSum & notCDom_sigExtraMask).bool()),
            notCDom_sig.eq(Cat(
                 notCDom_mainSig[:3].bool() | notCDom_reduced4SigExtra,
                 notCDom_mainSig>>3)),
            notCDom_completeCancellation.eq(
                    notCDom_sig[(sigWidth + 1):(sigWidth + 3)] == 0),
            notCDom_sign.eq(Mux(notCDom_completeCancellation,
                               roundingMode_min,
                               signProd ^ notCDom_signSigSum)),
        ]

        #/*-------------------------------------------------------------------
        #*-------------------------------------------------------------------*/
        comb += [\
            self.out_isZero.eq( notNaN_addZeros | \
                                (~CIsDominant & notCDom_completeCancellation)),
            out_sign.eq((specialCase                 & special_signOut) \
                     | (~specialCase &  CIsDominant & CDom_sign      ) \
                     | (~specialCase & ~CIsDominant & notCDom_sign   )),
            out_sExp.eq(Mux(CIsDominant, CDom_sExp, notCDom_sExp)),
            out_sig.eq(Mux(CIsDominant, CDom_sig, notCDom_sig)),
        ]

        return m

#/*------------------------------------------------------------------------
#*------------------------------------------------------------------------*/

class mulAddRecFNToRaw(Elaboratable):
    def __init__(expWidth=3, sigWidth=3):
        self.control = Signal(floatControlWidth, reset_less=True)
        self.op = Signal(2, reset_less=True)
        self.a = Signal(expWidth + sigWidth + 1, reset_less=True)
        self.b = Signal(expWidth + sigWidth + 1, reset_less=True)
        self.c = Signal(expWidth + sigWidth + 1, reset_less=True)
        self.roundingMode = Signal(3, reset_less=True)

        # output
        self.invalidExc = Signal(reset_less=True)
        self.out_isNaN = Signal(reset_less=True)
        self.out_isInf = Signal(reset_less=True)
        self.out_isZero = Signal(reset_less=True)
        self.out_sign = Signal(reset_less=True)
        self.out_sExp = Signal((expWidth + 2, True), reset_less=True)
        self.out_sig = Signal(sigWidth + 3, reset_less=True)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

        mulAddA = Signal(sigWidth, reset_less=True)
        mulAddB = Signal(sigWidth, reset_less=True)
        mulAddC = Signal(sigWidth*2, reset_less=True)
        intermed_compactState = Signal(6, reset_less=True)
        intermed_sExp = Signal(expWidth + 2, reset_less=True)
        wid = num_bits(sigWidth + 1)
        intermed_CDom_CAlignDist = Signal(wid, reset_less=True)
        intermed_highAlignedSigC = Signal((sigWidth + 2), reset_less=True)

        m.submodules.mar = mulAddToRaw_preMul = \
            mulAddRecFNToRaw_preMul(expWidth, sigWidth)

        comb += [\
            mulAddToRaw_preMul.control.eq(self.control),
            mulAddToRaw_preMul.op.eq(self.op),
            mulAddToRaw_preMul.a.eq(self.a),
            mulAddToRaw_preMul.b.eq(self.b),
            mulAddToRaw_preMul.roundingMode.eq(self.roundingMode),
            mulAddA.eq(mulAddToRaw_preMul.mulAddA),
            mulAddB.eq(mulAddToRaw_preMul.mulAddB),
            mulAddC.eq(mulAddToRaw_preMul.mulAddC),
            intermed_compactState.eq(mulAddToRaw_preMul.intermed_compactState),
            intermed_sExp.eq(mulAddToRaw_preMul.intermed_sExp),
            intermed_CDom_CAlignDist.eq(
                            mulAddToRaw_preMul.intermed_CDom_CAlignDist),
            intermed_highAlignedSigC.eq(
                            mulAddToRaw_preMul.intermed_highAlignedSigC),
        ]

        mulAddResult = Signal(sigWidth*2+1, reset_less=True)
        comb += mulAddResult.eq(mulAddA * mulAddB + mulAddC)

        m.submodules.marp = mulAddToRaw_postMul = \
                mulAddRecFNToRaw_postMul(expWidth, sigWidth)

        comb += [\
            mulAddRecFNToRaw_postMul.intermed_compactState.eq(
                        intermed_compactState),
            mulAddRecFNToRaw_postMul.intermed_sExp.eq(intermed_sExp),
            mulAddRecFNToRaw_postMul.intermed_CDom_CAlignDist.eq(
                        intermed_CDom_CAlignDist),
            mulAddRecFNToRaw_postMul.intermed_highAlignedSigC.eq(
                        intermed_highAlignedSigC),
            mulAddRecFNToRaw_postMul.mulAddResult.eq(mulAddResult),
            mulAddRecFNToRaw_postMul.roundingMode.eq(roundingMode),

            invalidExc.eq(mulAddRecFNToRaw_postMul.invalidExc),
            out_isNaN.eq(mulAddRecFNToRaw_postMul.out_isNaN),
            out_isInf.eq(mulAddRecFNToRaw_postMul.out_isInf),
            out_isZero.eq(mulAddRecFNToRaw_postMul.out_isZero),
            out_sign.eq(mulAddRecFNToRaw_postMul.out_sign),
            out_sExp.eq(mulAddRecFNToRaw_postMul.out_sExp),
            out_sig.eq(mulAddRecFNToRaw_postMul.out_sig),
        ]

        return m

"""
XXX TODO?

/*----------------------------------------------------------------------------
*----------------------------------------------------------------------------*/

module
    mulAddRecFN#(parameter expWidth = 3, parameter sigWidth = 3) (
        input [(`floatControlWidth - 1):0] control,
        input [1:0] op,
        input [(expWidth + sigWidth):0] a,
        input [(expWidth + sigWidth):0] b,
        input [(expWidth + sigWidth):0] c,
        input [2:0] roundingMode,
        output [(expWidth + sigWidth):0] out,
        output [4:0] exceptionFlags
    );

    wire invalidExc, out_isNaN, out_isInf, out_isZero, out_sign;
    wire signed [(expWidth + 1):0] out_sExp;
    wire [(sigWidth + 2):0] out_sig;
    mulAddRecFNToRaw#(expWidth, sigWidth)
        mulAddRecFNToRaw(
            control,
            op,
            a,
            b,
            c,
            roundingMode,
            invalidExc,
            out_isNaN,
            out_isInf,
            out_isZero,
            out_sign,
            out_sExp,
            out_sig
        );
    roundRawFNToRecFN#(expWidth, sigWidth, 0)
        roundRawOut(
            control,
            invalidExc,
            1'b0,
            out_isNaN,
            out_isInf,
            out_isZero,
            out_sign,
            out_sExp,
            out_sig,
            roundingMode,
            out,
            exceptionFlags
        );

endmodule
"""

