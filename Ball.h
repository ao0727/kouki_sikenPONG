#ifndef BALL_H
#define BALL_H

#include "DxLib.h"
#include "Paddle.h"
#include "Score.h"  
class Ball {
private:
    int x, y;       // �{�[���̈ʒu
    int speedX, speedY;  // �{�[���̑��x
    int size;       // �{�[���̃T�C�Y
    Score& score;   // Score �N���X�̎Q��

public:
    
    Ball(int startX, int startY, Score& scoreRef);

    // �{�[���̍X�V
    void Update();

    // �{�[���̕`��
    void Draw() const;

    // �p�h���Ƃ̏Փˏ���
    void CheckCollision(Paddle& player, Paddle& cpu);

    // �{�[���̃��Z�b�g
    void Reset(int startX, int startY);

    // �{�[����Y���W���擾
    int GetY() const { return y; }
};

#endif // BALL_H
