######################## BEGIN LICENSE BLOCK ########################
# The Original Code is Mozilla Communicator client code.
# 
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 1998
# the Initial Developer. All Rights Reserved.
# 
# Contributor(s):
#   Mark Pilgrim - port to Python
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA
######################### END LICENSE BLOCK #########################

import constants
from euctwfreq import EUCTWCharToFreqOrder, EUCTW_TABLE_SIZE, EUCTW_TYPICAL_DISTRIBUTION_RATIO
from euckrfreq import EUCKRCharToFreqOrder, EUCKR_TABLE_SIZE, EUCKR_TYPICAL_DISTRIBUTION_RATIO
from gb2312freq import GB2312CharToFreqOrder, GB2312_TABLE_SIZE, GB2312_TYPICAL_DISTRIBUTION_RATIO
from big5freq import Big5CharToFreqOrder, BIG5_TABLE_SIZE, BIG5_TYPICAL_DISTRIBUTION_RATIO
from jisfreq import JISCharToFreqOrder, JIS_TABLE_SIZE, JIS_TYPICAL_DISTRIBUTION_RATIO

ENOUGH_DATA_THRESHOLD = 1024
SURE_YES = 0.99
SURE_NO = 0.01

class CharDistributionAnalysis:
    def __init__(self):
        self._mCharToFreqOrder = None # Mapping table to get frequency order from char order (get from GetOrder())
        self._mTableSize = None # Size of above table
        self._mTypicalDistributionRatio = None # This is a constant value which varies from language to language, used in calculating confidence.  See http://www.mozilla.org/projects/intl/UniversalCharsetDetection.html for further detail.
        self.reset()
        
    def reset(self):
        """reset analyser, clear any state"""
        self._mDone = constants.False # If this flag is set to constants.True, detection is done and conclusion has been made
        self._mTotalChars = 0 # Total characters encountered
        self._mFreqChars = 0 # The number of characters whose frequency order is less than 512

    def feed(self, aStr, aCharLen):
        """feed a character with known length"""
        order = self.get_order(aStr) if aCharLen == 2 else -1
        if order >= 0:
            self._mTotalChars += 1
            # order is valid
            if order < self._mTableSize and self._mCharToFreqOrder[order] < 512:
                self._mFreqChars += 1

    def get_confidence(self):
        """return confidence based on existing data"""
        # if we didn't receive any character in our consideration range, return negative answer
        if self._mTotalChars <= 0:
            return SURE_NO

        if self._mTotalChars != self._mFreqChars:
            r = self._mFreqChars / ((self._mTotalChars - self._mFreqChars) * self._mTypicalDistributionRatio)
            if r < SURE_YES:
                return r

        # normalize confidence (we don't want to be 100% sure)
        return SURE_YES

    def got_enough_data(self):
        # It is not necessary to receive all data to draw conclusion. For charset detection,
        # certain amount of data is enough
        return self._mTotalChars > ENOUGH_DATA_THRESHOLD

    def get_order(self, aStr):
        # We do not handle characters based on the original encoding string, but 
        # convert this encoding string to a number, here called order.
        # This allows multiple encodings of a language to share one frequency table.
        return -1
    
class EUCTWDistributionAnalysis(CharDistributionAnalysis):
    def __init__(self):
        CharDistributionAnalysis.__init__(self)
        self._mCharToFreqOrder = EUCTWCharToFreqOrder
        self._mTableSize = EUCTW_TABLE_SIZE
        self._mTypicalDistributionRatio = EUCTW_TYPICAL_DISTRIBUTION_RATIO

    def get_order(self, aStr):
        # for euc-TW encoding, we are interested 
        #   first  byte range: 0xc4 -- 0xfe
        #   second byte range: 0xa1 -- 0xfe
        # no validation needed here. State machine has done that
        if aStr[0] >= '\xC4':
            return 94 * (ord(aStr[0]) - 0xC4) + ord(aStr[1]) - 0xA1
        else:
            return -1

class EUCKRDistributionAnalysis(CharDistributionAnalysis):
    def __init__(self):
        CharDistributionAnalysis.__init__(self)
        self._mCharToFreqOrder = EUCKRCharToFreqOrder
        self._mTableSize = EUCKR_TABLE_SIZE
        self._mTypicalDistributionRatio = EUCKR_TYPICAL_DISTRIBUTION_RATIO

    def get_order(self, aStr):
        # for euc-KR encoding, we are interested 
        #   first  byte range: 0xb0 -- 0xfe
        #   second byte range: 0xa1 -- 0xfe
        # no validation needed here. State machine has done that
        if aStr[0] >= '\xB0':
            return 94 * (ord(aStr[0]) - 0xB0) + ord(aStr[1]) - 0xA1
        else:
            return -1;

class GB2312DistributionAnalysis(CharDistributionAnalysis):
    def __init__(self):
        CharDistributionAnalysis.__init__(self)
        self._mCharToFreqOrder = GB2312CharToFreqOrder
        self._mTableSize = GB2312_TABLE_SIZE
        self._mTypicalDistributionRatio = GB2312_TYPICAL_DISTRIBUTION_RATIO

    def get_order(self, aStr):
        # for GB2312 encoding, we are interested 
        #  first  byte range: 0xb0 -- 0xfe
        #  second byte range: 0xa1 -- 0xfe
        # no validation needed here. State machine has done that
        if (aStr[0] >= '\xB0') and (aStr[1] >= '\xA1'):
            return 94 * (ord(aStr[0]) - 0xB0) + ord(aStr[1]) - 0xA1
        else:
            return -1;

class Big5DistributionAnalysis(CharDistributionAnalysis):
    def __init__(self):
        CharDistributionAnalysis.__init__(self)
        self._mCharToFreqOrder = Big5CharToFreqOrder
        self._mTableSize = BIG5_TABLE_SIZE
        self._mTypicalDistributionRatio = BIG5_TYPICAL_DISTRIBUTION_RATIO

    def get_order(self, aStr):
        if aStr[0] < '\xA4':
            return -1
        if aStr[1] >= '\xA1':
            return 157 * (ord(aStr[0]) - 0xA4) + ord(aStr[1]) - 0xA1 + 63
        else:
            return 157 * (ord(aStr[0]) - 0xA4) + ord(aStr[1]) - 0x40

class SJISDistributionAnalysis(CharDistributionAnalysis):
    def __init__(self):
        CharDistributionAnalysis.__init__(self)
        self._mCharToFreqOrder = JISCharToFreqOrder
        self._mTableSize = JIS_TABLE_SIZE
        self._mTypicalDistributionRatio = JIS_TYPICAL_DISTRIBUTION_RATIO

    def get_order(self, aStr):
        # for sjis encoding, we are interested 
        #   first  byte range: 0x81 -- 0x9f , 0xe0 -- 0xfe
        #   second byte range: 0x40 -- 0x7e,  0x81 -- oxfe
        # no validation needed here. State machine has done that
        if (aStr[0] >= '\x81') and (aStr[0] <= '\x9F'):
            order = 188 * (ord(aStr[0]) - 0x81)
        elif (aStr[0] >= '\xE0') and (aStr[0] <= '\xEF'):
            order = 188 * (ord(aStr[0]) - 0xE0 + 31)
        else:
            return -1;
        order = order + ord(aStr[1]) - 0x40
        if aStr[1] > '\x7F':
            order =- 1
        return order

class EUCJPDistributionAnalysis(CharDistributionAnalysis):
    def __init__(self):
        CharDistributionAnalysis.__init__(self)
        self._mCharToFreqOrder = JISCharToFreqOrder
        self._mTableSize = JIS_TABLE_SIZE
        self._mTypicalDistributionRatio = JIS_TYPICAL_DISTRIBUTION_RATIO

    def get_order(self, aStr):
        # for euc-JP encoding, we are interested 
        #   first  byte range: 0xa0 -- 0xfe
        #   second byte range: 0xa1 -- 0xfe
        # no validation needed here. State machine has done that
        if aStr[0] >= '\xA0':
            return 94 * (ord(aStr[0]) - 0xA1) + ord(aStr[1]) - 0xa1
        else:
            return -1
