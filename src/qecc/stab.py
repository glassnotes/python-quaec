#!/usr/bin/python
# -*- coding: utf-8 -*-
##
# stab.py: Classes and methods encapsulating and manipulating stabilizer codes.
##
# © 2012 Christopher E. Granade (cgranade@gmail.com) and
#     Ben Criger (bcriger@gmail.com).
# This file is a part of the QuaEC project.
# Licensed under the AGPL version 3.
##
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

## IMPORTS ##

import operator as op

import PauliClass as p # Sorry for the confusing notation here.
import CliffordClass as c
import paulicollections as pc


from singletons import EmptyClifford, Unspecified

import warnings

## ALL ##

__all__ = [
    'StabilizerCode'
]

## CLASSES ##

class StabilizerCode(object):
    r"""
    TODO
    """
    
    def __init__(self, group_generators, logical_xs, logical_zs):
        self.group_generators = pc.PauliList(*group_generators)
        self.logical_xs = pc.PauliList(*logical_xs)
        self.logical_zs = pc.PauliList(*logical_zs)
        
    def __repr__(self):
        return "<[[{n}, {k}, {d}]] StabilizerCode at {id:0x}>".format(
            n=self.nq, k=self.nq_logical,
            d=self.distance if self.nq < 6 else "?",
            id=id(self)
        )
    
    def __str__(self):
        return "S = <{group_generators}>\nXbars = {0.logical_xs}\nZbars = {0.logical_zs}".format(
            self,
            group_generators=", ".join(map(str, self.group_generators)))
        
    @property
    def nq(self):
        """
        TODO
        """
        return len(iter(gen for gen in self.group_generators if gen is not Unspecified).next())
        
    @property
    def n_constraints(self):
        return len(self.group_generators)
        
    @property
    def nq_logical(self):
        return self.nq - self.n_constraints
        
    @property
    def distance(self):
        """
        Warning: this property is currently very slow to compute.
        """
        return min(P.wt for P in self.normalizer_group(mod_s=True))
 
    def stabilizer_group(self, coset_rep=None):
        return self.group_generators.generated_group(coset_rep=coset_rep)
        
    def logical_pauli_group(self, incl_identity=True):
        return p.from_generators(self.logical_xs + self.logical_zs, incl_identity=incl_identity)
        
    def normalizer_group(self, mod_s=False):
        r"""
        Returns all elements of the normalizer of the stabilizer group. If
        ``mod_s`` is ``True``, returns the set :math:`N(S)\\S`.
        """
        for Pbar in self.logical_pauli_group(incl_identity=not mod_s):
            for normalizer_element in self.stabilizer_group(coset_rep=Pbar):
                yield normalizer_element
        
    def encoding_cliffords(self):
        C = c.Clifford(self.logical_xs + ([Unspecified] * self.n_constraints), self.logical_zs + self.group_generators)
        return C.constraint_completions()

    def block_logical_pauli(self, P):
        r"""
        Given a Pauli operator :math:`P` acting on :math:`k`, finds a Pauli
        operator :math:`\overline{P}` on :math:`nk` qubits that corresponds
        to the logical operator acting across :math:`k` blocks of this code.
        
        Note that this method is only supported for single logical qubit codes.
        """
        
        if self.nq_logical > 1:
            raise NotImplementedError("Mapping of logical Pauli operators is currently only supported for single-qubit codes.")
        
        # TODO: test that phases are handled correctly.
        
        # FIXME: cache this dictionary.
        replace_dict = {
            'I': p.eye_p(self.nq),
            'X': self.logical_xs[0],
            'Y': (self.logical_xs[0] * self.logical_zs[0]).mul_phase(1),
            'Z': self.logical_zs[0]
        }
        
        # FIXME: using eye_p(0) is a hack.
        return reduce(op.and_, 
                (replace_dict[sq_op] for sq_op in P.op),
                p.eye_p(0))

    def concatenate(self,other):
        """
        Returns the stabilizer for a concatenated code, given the 
        stabilizers for two codes. At this point, it only works for two
        k=1 codes.
        """
        
        if self.nq_logical > 1 or other.nq_logical > 1:
            raise NotImplementedError("Concatenation is currently only supported for single-qubit codes.")
        
        nq_self = self.nq
        nq_other = other.nq
        nq_new = nq_self * nq_other
        
        # To obtain the new generators, we must apply the stabilizer generators
        # to each block of the inner code (self), as well as the stabilizer
        # generators of the outer code (other), using the inner logical Paulis
        # for the outer stabilizer generators.
        
        # Making the stabilizer generators from the inner (L0) code is straight-
        # forward: we repeat the code other.nq times, once on each block of the
        # outer code. We use that PauliList supports tensor products.
        new_generators = sum(
            (
                p.eye_p(nq_self * k) & self.group_generators & p.eye_p(nq_self * (nq_other - k - 1))
                for k in range(nq_other)
            ),
            pc.PauliList())
                
        # Each of the stabilizer generators due to the outer (L1) code can be
        # found by computing the block-logical operator across multiple L0
        # blocks, as implemented by StabilizerCode.block_logical_pauli.
        new_generators += map(self.block_logical_pauli, other.group_generators)
            
        # In the same way, the logical operators are also found by mapping L1
        # operators onto L0 qubits.
        
        # This completes the definition of the concatenated code, and so we are
        # done.
        
        return StabilizerCode(new_generators,
            logical_xs=map(self.block_logical_pauli, other.logical_xs),
            logical_zs=map(self.block_logical_pauli, other.logical_zs)
        )

    ## COMMON CODES ##

    @staticmethod
    def flip_code(dist, stab_kind='Z'):
        nq=2*dist+1
        return StabilizerCode(
            ['I'*j + (stab_kind * 2) + 'I'*(nq-j-2) for j in range(nq-1)],
            ['X'*nq], ['Z'*nq]
        )

    @staticmethod
    def bit_flip_code(x_dist):
        return StabilizerCode.flip_code(x_dist, stab_kind='Z')

    @staticmethod
    def phase_flip_code(z_dist):
        return StabilizerCode.flip_code(z_dist, stab_kind='X')

    @staticmethod
    def perfect_5q_code():
        return StabilizerCode(
            [
                'XZZXI',
                'IXZZX',
                'XIXZZ',
                'ZXIXZ'
            ],
            ['XXXXX'], ['ZZZZZ']
        )

    @staticmethod
    def steane_code():
        return StabilizerCode(
            [
                'XXXXIII',
                'XXIIXXI',
                'XIXIXIX',
                'ZZZZIII',
                'ZZIIZZI',
                'ZIZIZIZ'                
            ],
            ['XXXXXXX'], ['ZZZZZZZ']
        )

    @staticmethod
    def shor_code():
        return StabilizerCode.bit_flip_code(1).concatenate(StabilizerCode.phase_flip_code(1))        

    @staticmethod
    def css_code(C1, C2):
        raise NotImplementedError("Not yet implemented.")

    @staticmethod
    def reed_muller_code(r,t):
        raise NotImplementedError("Coming Soon: Reed-Muller Codes")

    @staticmethod
    def reed_solomon_code(r,t):
        raise NotImplementedError("Coming Soon: Reed-Solomon Codes")
