#ifndef PADDLE_H
#define PADDLE_H

#include "DxLib.h"
//#include "Ball.h"  // Ball �N���X�̃C���N���[�h

class Ball;

class Paddle {
private:
    int x, y;       // �p�h���̈ʒu
    int width, height;  // �p�h���̃T�C�Y
    int speed;      // �p�h���̈ړ����x

public:
    // �R���X�g���N�^
    Paddle(int startX, int startY);

    // �v���C���[�̑���
    void Update(int upKey, int downKey);

    // CPU�̑���
    void AIControl( const Ball& ball);  // Ball �N���X���Q��

    // �p�h���̕`��
    void Draw() const;

    // �p�h���̈ʒu���
    int GetX() const;
    int GetY() const;
    int GetWidth() const;
    int GetHeight() const;
};

#endif // PADDLE_H
