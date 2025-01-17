#include "Ball.h"
#include "DxLib.h"

#include <cstdlib> 
#include <ctime>   

//�{�[���̋�����X�R�A�Ǘ�������

Ball::Ball(int startX, int startY, Score& scoreRef)
    : x(startX), y(startY), speedX(5), speedY(5), size(10), score(scoreRef) {}

void Ball::Update() {
    // �{�[���̈ʒu�X�V
    x += speedX;
    y += speedY;

    // ��ʒ[�ł̒��˕Ԃ�
    if (y <= 0 || y >= 480 - size) {
        speedY = -speedY; // ����
    }

    // ���E�̕ǂɓ��������瓾�_�����Z
    if (x <= 0) {
        score.AddCpuScore();  // ���ǂɓ���������CPU�̓��_
        Reset(300, 240);      // �{�[�������Z�b�g
    }
    if (x >= 640 - size) {
        score.AddPlayerScore(); // �E�ǂɓ���������v���C���[�̓��_
        Reset(300, 240);        // �{�[�������Z�b�g
    }
}

void Ball::Draw() const {
    DrawCircle(x, y, size, GetColor(255, 255, 255), TRUE); // �{�[����`��
}

void Ball::CheckCollision(Paddle& player, Paddle& cpu) {
    // �v���C���[��CPU�p�h���Ƃ̏Փ˔���
    if (x - size < player.GetX() + player.GetWidth() &&
        x + size > player.GetX() &&
        y > player.GetY() &&
        y < player.GetY() + player.GetHeight()) {
        speedX = -speedX; // ���������̑��x���]
    }

    // CPU�̃p�h���ƃ{�[���̏Փ�
    if (x + size > cpu.GetX() &&
        x - size < cpu.GetX() + cpu.GetWidth() &&
        y > cpu.GetY() &&
        y < cpu.GetY() + cpu.GetHeight()) {
        speedX = -speedX; // ���������̑��x���]
    }
}

void Ball::Reset(int startX, int startY) {
    x = startX;
    y = startY;
    /*speedX = 5;
    speedY = 5;*/

    int randomAngle = rand() % 120 + 30;
    double radian = randomAngle * 3.14159265 / 180.0; // �p�x�����W�A���ɕϊ�

    // X, Y �̑��x���v�Z
    speedX = (rand() % 2 == 0 ? 1 : -1) * 5 * cos(radian); // X�����̑��x
    speedY = 5 * sin(radian);



}
