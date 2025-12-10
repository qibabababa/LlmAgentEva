#!/usr/bin/env python3
# -*- coding: utf-8 -*-

GLOBAL_CONSTANT_VALUE = 100

def addTwoNumbers(first_number, second_number):
    sum_result = first_number + second_number
    return sum_result


def multiplyTwoNumbers(first_number, second_number):

    product_result = first_number * second_number
    return product_result


def processUserInput(user_input_list):
    # 第一步：加法
    added_list = [addTwoNumbers(item, GLOBAL_CONSTANT_VALUE) for item in user_input_list]
    # 第二步：乘法
    multiplied_list = [multiplyTwoNumbers(item, 2) for item in added_list]
    return multiplied_list

class SimpleMathHelper:

    def __init__(self, base_value=GLOBAL_CONSTANT_VALUE):
        self.base_value = base_value

    def squareNumber(self, number_to_square):
        squared_val = number_to_square ** 2
        return squared_val

    def addBaseAndSquare(self, value):
        """
        先加上 base_value，再求平方
        """
        intermediate_val = addTwoNumbers(value, self.base_value)
        return self.squareNumber(intermediate_val)

if __name__ == "__main__":
    sample_input = [1, 2, 3, 4, 5]
    print("原始列表:", sample_input)

    processed_output = processUserInput(sample_input)
    print("函数处理结果:", processed_output)

    helper = SimpleMathHelper()
    class_output = [helper.addBaseAndSquare(x) for x in sample_input]
    print("类方法处理结果:", class_output)
