from data.signature_vector.attribute import VariantAttribute, InvariantAttribute

class SignatureVector:
    """ A class composed of variant and invariant attributes that uniquely defines an image in the contrastive lighting dataset."""
    def __init__(self, variant_attributes: tuple[VariantAttribute], invariant_attributes: tuple[InvariantAttribute]):
        self.variant_attributes = variant_attributes
        self.invariant_attributes = invariant_attributes