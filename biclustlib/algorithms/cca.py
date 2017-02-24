"""
    biclustlib: A Python library of biclustering algorithms and evaluation measures.
    Copyright (C) 2017  Victor Alexandre Padilha

    This file is part of biclustlib.

    biclustlib is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    biclustlib is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from _base import BaseBiclusteringAlgorithm
from ..models import Bicluster, Biclustering

import numpy as np

class ChengChurchAlgorithm(BaseBiclusteringAlgorithm):
    """Cheng and Church's Algorithm (CCA)

    CCA searches for maximal submatrices with a Mean Squared Residue value below a pre-defined threshold.

    Reference
    ----------
    Cheng, Y. and Church, G. M. (2000). Biclustering of expression data. In Proceedings of the 8th
    International Conference on Intelligence Systems for Molecular Biology, volume 8, pages 93-103.
    AAAI Press.

    Parameters
    ----------
    num_biclusters : int, default: 10
        Number of biclusters to be found.

    msr_threshold : float, default: 0.1
        Maximum mean squared residue accepted (delta parameter in the original paper).

    multiple_node_deletion_threshold : float, default: 1.2
        Scaling factor to remove multiple rows or columns (alpha parameter in the original paper).

    data_min_cols : int, default: 100
        Minimum number of dataset columns required to perform multiple column deletion.
    """

    def __init__(self, num_biclusters=10, msr_threshold=0.1, multiple_node_deletion_threshold=1.2, data_min_cols=100):
        self.num_biclusters = num_biclusters
        self.msr_threshold = msr_threshold
        self.multiple_node_deletion_threshold = multiple_node_deletion_threshold
        self.data_min_cols = data_min_cols

    def run(self, data):
        """Compute biclustering.

        Parameters
        ----------
        data : numpy.ndarray
        """
        self._validate_parameters()

        data = np.copy(data)

        num_rows, num_cols = data.shape
        min_value = np.min(data)
        max_value = np.max(data)

        biclusters = []

        for i in range(self.num_biclusters):
            rows = np.ones(num_rows, dtype=np.bool)
            cols = np.ones(num_cols, dtype=np.bool)

            self._multiple_node_deletion(data, rows, cols)
            self._single_node_deletion(data, rows, cols)
            self._node_addition(data, rows, cols)

            row_indices = np.where(rows)[0]
            col_indices = np.where(cols)[0]

            if len(row_indices) == 0 or len(col_indices) == 0:
                break

            # masking matrix values
            if i < self.num_biclusters - 1:
                bicluster_shape = (len(row_indices), len(col_indices))
                data[row_indices[:, np.newaxis], col_indices] = np.random.uniform(low=min_value, high=max_value, size=bicluster_shape)

            biclusters.append(Bicluster(row_indices, col_indices))

        return Biclustering(biclusters)

    def _single_node_deletion(self, data, rows, cols):
        """Performs the single row/column deletion step (this is a direct implementation of the Algorithm 1 described in
        the original paper)"""
        msr, row_msr, col_msr = self._calculate_msr(data, rows, cols)

        while msr > self.msr_threshold:
            row_indices = np.where(rows)[0]
            col_indices = np.where(cols)[0]

            row_max_msr = np.argmax(row_msr)
            col_max_msr = np.argmax(col_msr)

            if row_msr[row_max_msr] >= col_msr[col_max_msr]:
                row2remove = row_indices[row_max_msr]
                rows[row2remove] = False
            else:
                col2remove = col_indices[col_max_msr]
                cols[col2remove] = False

            msr, row_msr, col_msr = self._calculate_msr(data, rows, cols)

    def _multiple_node_deletion(self, data, rows, cols):
        """Performs the multiple row/column deletion step (this is a direct implementation of the Algorithm 2 described in
        the original paper)"""
        msr, row_msr, col_msr = self._calculate_msr(data, rows, cols)

        if msr <= self.msr_threshold:
            stop = True
        else:
            stop = False

        while not stop:
            cols_old = np.copy(cols)
            rows_old = np.copy(rows)

            row_indices = np.where(rows)[0]
            rows2remove = row_indices[np.where(row_msr > self.multiple_node_deletion_threshold * msr)]
            rows[rows2remove] = False

            if len(cols) >= self.data_min_cols:
                col_indices = np.where(cols)[0]
                cols2remove = col_indices[np.where(col_msr > self.multiple_node_deletion_threshold * msr)]
                cols[cols2remove] = False
            else:
                cols2remove = np.array([])

            msr, row_msr, col_msr = self._calculate_msr(data, rows, cols)

            # Tests if the new MSR value is smaller than the acceptable MSR threshold.
            # Tests if no rows and no columns were removed during this iteration.
            # If one of the conditions is true the loop must stop, otherwise it will become an infinite loop.
            if msr <= self.msr_threshold or (np.all(rows == rows_old) and np.all(cols == cols_old)):
                stop = True

    def _node_addition(self, data, rows, cols):
        """Performs the row/column addition step (this is a direct implementation of the Algorithm 3 described in
        the original paper)"""
        stop = False

        while not stop:
            cols_old = np.copy(cols)
            rows_old = np.copy(rows)

            msr, _, _ = self._calculate_msr(data, rows, cols)
            col_msr = self._calculate_msr_col_addition(data, rows, cols)
            cols2add = np.where(col_msr <= msr)[0]
            cols[cols2add] = True

            msr, _, _ = self._calculate_msr(data, rows, cols)
            row_msr, row_inverse_msr = self._calculate_msr_row_addition(data, rows, cols)
            rows2add = np.where(np.logical_or(row_msr <= msr, row_inverse_msr <= msr))[0]
            rows[rows2add] = True

            if np.all(rows == rows_old) and np.all(cols == cols_old):
                stop = True

    def _calculate_msr(self, data, rows, cols):
        """Calculate the mean squared residues of the rows, of the columns and of the full data matrix."""
        sub_data = data[rows][:, cols]

        data_mean = np.mean(sub_data)
        row_means = np.mean(sub_data, axis=1)
        col_means = np.mean(sub_data, axis=0)

        residues = sub_data - row_means[:, np.newaxis] - col_means + data_mean
        squared_residues = residues * residues

        msr = np.mean(squared_residues)
        row_msr = np.mean(squared_residues, axis=1)
        col_msr = np.mean(squared_residues, axis=0)

        return msr, row_msr, col_msr

    def _calculate_msr_col_addition(self, data, rows, cols):
        """Calculate the mean squared residues of the rows, of the inverse of the rows and of the columns for
        the node addition step."""
        data_mean = np.mean(data[rows][:, cols])
        row_means = np.mean(data[:, cols], axis=1)
        col_means = np.mean(data[rows], axis=0)

        col_residues = data - row_means[:, np.newaxis] - col_means + data_mean
        col_squared_residues = col_residues * col_residues
        col_msr = np.mean(col_squared_residues, axis=0)

        return col_msr

    def _calculate_msr_row_addition(self, data, rows, cols):
        """Calculate the mean squared residues of the rows, of the inverse of the rows and of the columns for
        the node addition step."""
        data_mean = np.mean(data[rows][:, cols])
        row_means = np.mean(data[:, cols], axis=1)
        col_means = np.mean(data[rows], axis=0)

        row_residues = data - row_means[:, np.newaxis] - col_means + data_mean
        row_squared_residues = row_residues * row_residues
        row_msr = np.mean(row_squared_residues, axis=1)

        inverse_residues = -data + row_means[:, np.newaxis] - col_means + data_mean
        row_inverse_squared_residues = inverse_residues * inverse_residues
        row_inverse_msr = np.mean(row_inverse_squared_residues, axis=1)

        return row_msr, row_inverse_msr

    def _validate_parameters(self):
        if self.num_biclusters <= 0:
            raise ValueError("'num_biclusters' must be greater than zero")

        if self.msr_threshold < 0.0:
            raise ValueError("'msr_threshold' must be greater than or equal to zero")

        if self.multiple_node_deletion_threshold < 1.0:
            raise ValueError("'multiple_node_deletion_threshold' must be greater than or equal to 1")