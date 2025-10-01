import random
from .attribute import VariantAttribute, InvariantAttribute

class SignatureVector:
    """ A class composed of variant and invariant attributes that uniquely defines an image in the contrastive lighting dataset."""
    def __init__(self, variant_attributes: tuple[VariantAttribute, ...], invariant_attributes: tuple[InvariantAttribute, ...]):
        self.variant_attributes = variant_attributes
        self.invariant_attributes = invariant_attributes

class SignatureVectorFactory:
    def __init__(
        self,
        variant_attributes_and_freedom: tuple[tuple[type[VariantAttribute], bool], ...],
        invariant_attributes_and_freedom: tuple[tuple[type[InvariantAttribute], bool], ...],
        rng: random.Random = random.Random(0)
    ):
        self.rng = rng
        # TODO: Clean this up some day :)
        self.list_fixed_variant_attributes = []
        self.free_variant_indices = []
        self.free_variant_classes = []
        i = 0
        for attr_type, is_free in variant_attributes_and_freedom:
            if not is_free:
                self.list_fixed_variant_attributes.append(attr_type.sample_value(self.rng))
            else:
                self.list_fixed_variant_attributes.append(None)
                self.free_variant_indices.append(i)
                self.free_variant_classes.append(attr_type)
            i += 1

        self.free_invariant_indices = []
        i = 0
        self.list_fixed_invariant_attributes = []
        self.free_invariant_classes = []
        for attr_type, is_free in invariant_attributes_and_freedom:
            if not is_free:
                self.list_fixed_invariant_attributes.append(attr_type.sample_value(self.rng))
            else:
                self.list_fixed_invariant_attributes.append(None)
                self.free_invariant_indices.append(i)
                self.free_invariant_classes.append(attr_type)
            i += 1
        
    def sample_signature_vector(self, sv_cls: type[SignatureVector] = SignatureVector) -> SignatureVector:
        """Sample a signature vector instance.

        Parameters
        ----------
        sv_cls : type[SignatureVector], optional
            The concrete subclass of `SignatureVector` to instantiate. Must accept
            (variant_attributes: tuple[VariantAttribute, ...], invariant_attributes: tuple[InvariantAttribute, ...])
            in its constructor. Defaults to the base `SignatureVector`.
        """
        variant_attributes = list(self.list_fixed_variant_attributes)
        invariant_attributes = list(self.list_fixed_invariant_attributes)

        for i in self.free_variant_indices:
            variant_attributes[i] = self.free_variant_classes[i].sample_value(self.rng)

        for i in self.free_invariant_indices:
            invariant_attributes[i] = self.free_invariant_classes[i].sample_value(self.rng)

        return sv_cls(
            variant_attributes=tuple(variant_attributes),
            invariant_attributes=tuple(invariant_attributes)
        )
